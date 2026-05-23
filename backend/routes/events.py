"""
WebSocket Events
Uses Flask-SocketIO. A background thread ticks every WS_EMIT_INTERVAL_S seconds
and broadcasts the full telemetry snapshot to all connected clients.

The client can also emit control events (change drive mode, reset trip, etc.)
and the server responds via SocketIO acknowledgements.
"""
import time
import threading
from flask_socketio import emit
from backend.config import Config
from backend.models.database import log_telemetry


_engine     = None
_socketio   = None
_bg_thread  = None
_thread_lock = threading.Lock()


def set_engine(engine):
    global _engine
    _engine = engine


def register_ws_events(socketio):
    """Bind all SocketIO event handlers and start the background emit loop."""
    global _socketio
    _socketio = socketio

    @socketio.on("connect")
    def handle_connect():
        print(f"[WS] Client connected: {id(emit)}")
        # Send current config immediately on connect
        from backend.config import Config
        emit("config", {
            "battery_capacity_kwh": Config.BATTERY_CAPACITY_KWH,
            "motor_max_power_kw":   Config.MOTOR_MAX_POWER_KW,
            "motor_max_rpm":        Config.MOTOR_MAX_RPM,
            "drive_modes":          list(Config.DRIVE_MODES.keys()),
        })
        # Kick off the background thread (only once)
        global _bg_thread
        with _thread_lock:
            if _bg_thread is None or not _bg_thread.is_alive():
                _bg_thread = socketio.start_background_task(_emit_loop)

    @socketio.on("disconnect")
    def handle_disconnect():
        print("[WS] Client disconnected")

    @socketio.on("set_drive_mode")
    def handle_set_mode(data):
        mode = data.get("mode", "NORMAL").upper()
        if _engine and mode in Config.DRIVE_MODES:
            _engine.drive_mode = mode
            emit("drive_mode_changed", {"mode": mode})

    @socketio.on("reset_trip")
    def handle_reset_trip():
        if _engine:
            _engine.trip_distance  = 0.0
            _engine.trip_start     = time.time()
            _engine.battery.energy_discharged_kWh = 0.0
            _engine.battery.energy_recovered_kWh  = 0.0
            _engine._consumption_window = []
            emit("trip_reset", {"ts": time.time()})

    @socketio.on("request_snapshot")
    def handle_request_snapshot():
        """On-demand snapshot — useful on reconnect."""
        if _engine:
            emit("telemetry", _engine.snapshot())


def _emit_loop():
    """
    Background task: produces telemetry at the configured interval.
    Runs as a greenlet (eventlet/gevent) or thread depending on async_mode.
    """
    while True:
        try:
            if _engine and _socketio:
                snapshot = _engine.snapshot()
                log_telemetry(snapshot)                  # persist to SQLite
                _socketio.emit("telemetry", snapshot)    # broadcast to all clients
        except Exception as exc:
            print(f"[WS] Emit loop error: {exc}")
        time.sleep(Config.WS_EMIT_INTERVAL_S)
