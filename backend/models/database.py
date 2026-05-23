"""
Database Models — SQLite via sqlite3 (no ORM needed for v1)

Schema:
  trips           — one row per driving trip (start/end times, summary)
  telemetry_log   — high-frequency snapshots (downsampled to 1/5 s to save space)
  fault_events    — timestamped fault/alert occurrences
"""
import sqlite3
import os
import json
import time
from backend.config import Config


def get_connection() -> sqlite3.Connection:
    """Return a thread-safe SQLite connection with row_factory set."""
    db_path = Config.DATABASE_PATH
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # better concurrent read/write
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db() -> None:
    """Create tables if they do not exist."""
    conn = get_connection()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS trips (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at      REAL    NOT NULL,
                ended_at        REAL,
                distance_km     REAL    DEFAULT 0,
                energy_kwh      REAL    DEFAULT 0,
                avg_speed_kmh   REAL    DEFAULT 0,
                max_speed_kmh   REAL    DEFAULT 0,
                regen_kwh       REAL    DEFAULT 0,
                soc_start       REAL,
                soc_end         REAL,
                drive_modes     TEXT,        -- JSON list of modes used
                notes           TEXT
            );

            CREATE TABLE IF NOT EXISTS telemetry_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id         INTEGER REFERENCES trips(id),
                ts              REAL    NOT NULL,
                speed_kmh       REAL,
                soc             REAL,
                pack_voltage    REAL,
                current_A       REAL,
                battery_temp    REAL,
                motor_temp      REAL,
                power_kw        REAL,
                range_km        REAL
            );

            CREATE TABLE IF NOT EXISTS fault_events (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id         INTEGER REFERENCES trips(id),
                ts              REAL    NOT NULL,
                code            TEXT    NOT NULL,
                message         TEXT,
                severity        TEXT,
                value           REAL,
                unit            TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_telemetry_trip ON telemetry_log(trip_id);
            CREATE INDEX IF NOT EXISTS idx_faults_trip    ON fault_events(trip_id);
        """)
    conn.close()


# ─── Trip API ──────────────────────────────────────────────────────────────

def start_trip(soc_start: float) -> int:
    """Insert a new trip row, return its ID."""
    conn = get_connection()
    with conn:
        cur = conn.execute(
            "INSERT INTO trips (started_at, soc_start) VALUES (?, ?)",
            (time.time(), soc_start)
        )
        trip_id = cur.lastrowid
    conn.close()
    return trip_id


def end_trip(trip_id: int, summary: dict) -> None:
    """Close a trip with final statistics."""
    conn = get_connection()
    with conn:
        conn.execute("""
            UPDATE trips SET
                ended_at      = ?,
                distance_km   = ?,
                energy_kwh    = ?,
                avg_speed_kmh = ?,
                max_speed_kmh = ?,
                regen_kwh     = ?,
                soc_end       = ?,
                drive_modes   = ?
            WHERE id = ?
        """, (
            time.time(),
            summary.get("distance_km", 0),
            summary.get("energy_kwh", 0),
            summary.get("avg_speed_kmh", 0),
            summary.get("max_speed_kmh", 0),
            summary.get("regen_kwh", 0),
            summary.get("soc_end", 0),
            json.dumps(summary.get("drive_modes", [])),
            trip_id,
        ))
    conn.close()


def get_trips(limit: int = 20) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM trips ORDER BY started_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_trip_detail(trip_id: int) -> dict:
    conn = get_connection()
    trip = conn.execute("SELECT * FROM trips WHERE id = ?", (trip_id,)).fetchone()
    logs = conn.execute(
        "SELECT * FROM telemetry_log WHERE trip_id = ? ORDER BY ts", (trip_id,)
    ).fetchall()
    faults = conn.execute(
        "SELECT * FROM fault_events WHERE trip_id = ? ORDER BY ts", (trip_id,)
    ).fetchall()
    conn.close()
    return {
        "trip":   dict(trip) if trip else {},
        "logs":   [dict(r) for r in logs],
        "faults": [dict(r) for r in faults],
    }


# ─── Logging API ──────────────────────────────────────────────────────────

_log_counter = 0          # only log every 5th tick (≈ 2.5 s at 500 ms interval)
_active_trip_id = None

def log_telemetry(snapshot: dict) -> None:
    """Downsample and store a telemetry snapshot."""
    global _log_counter, _active_trip_id

    # Start a trip if none is active
    if _active_trip_id is None:
        _active_trip_id = start_trip(snapshot["battery"]["soc"])

    _log_counter += 1
    if _log_counter % 5 != 0:   # store every 5th tick
        return

    conn = get_connection()
    with conn:
        conn.execute("""
            INSERT INTO telemetry_log
                (trip_id, ts, speed_kmh, soc, pack_voltage, current_A,
                 battery_temp, motor_temp, power_kw, range_km)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            _active_trip_id,
            snapshot["ts"],
            snapshot["vehicle"]["speed_kmh"],
            snapshot["battery"]["soc"],
            snapshot["battery"]["pack_voltage"],
            snapshot["battery"]["current"],
            snapshot["battery"]["temperature"],
            snapshot["motor"]["temperature"],
            snapshot["motor"]["power_kw"],
            snapshot["vehicle"]["range_km"],
        ))

        # Log CRITICAL/FAULT alerts immediately
        for alert in snapshot.get("alerts", []):
            if alert["severity"] in ("CRITICAL", "FAULT"):
                conn.execute("""
                    INSERT INTO fault_events
                        (trip_id, ts, code, message, severity, value, unit)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    _active_trip_id,
                    snapshot["ts"],
                    alert["code"],
                    alert["message"],
                    alert["severity"],
                    alert.get("value"),
                    alert.get("unit", ""),
                ))
    conn.close()
