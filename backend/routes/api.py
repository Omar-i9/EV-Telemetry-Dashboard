"""
REST API Routes  (/api/...)
All endpoints return JSON. The WebSocket is the primary real-time channel;
these endpoints serve initial page load, trip history, and control commands.
"""
from flask import Blueprint, jsonify, request
from backend.models.database import get_trips, get_trip_detail, end_trip
from backend.services.alert_system import AlertSystem

api_bp = Blueprint("api", __name__)

# Will be injected by app.py after engine is created
_engine = None

def set_engine(engine):
    global _engine
    _engine = engine


# ─── Telemetry snapshot (HTTP fallback if WS unavailable) ────────────────────
@api_bp.route("/telemetry", methods=["GET"])
def get_telemetry():
    if _engine is None:
        return jsonify({"error": "Engine not initialised"}), 503
    return jsonify(_engine.snapshot())


# ─── Vehicle config (for the frontend to read parameters) ────────────────────
@api_bp.route("/config", methods=["GET"])
def get_config():
    from backend.config import Config
    return jsonify({
        "battery_capacity_kwh": Config.BATTERY_CAPACITY_KWH,
        "motor_max_power_kw":   Config.MOTOR_MAX_POWER_KW,
        "motor_max_torque_nm":  Config.MOTOR_MAX_TORQUE_NM,
        "motor_max_rpm":        Config.MOTOR_MAX_RPM,
        "vehicle_mass_kg":      Config.VEHICLE_MASS_KG,
        "drive_modes":          list(Config.DRIVE_MODES.keys()),
        "fault_codes":          Config.FAULT_CODES,
        "alert_thresholds": {
            "soc_low":            Config.ALERT_SOC_LOW,
            "soc_critical":       Config.ALERT_SOC_CRITICAL,
            "battery_temp_warn":  Config.ALERT_BATTERY_TEMP_WARN,
            "battery_temp_crit":  Config.ALERT_BATTERY_TEMP_CRIT,
            "motor_temp_warn":    Config.ALERT_MOTOR_TEMP_WARN,
            "motor_temp_crit":    Config.ALERT_MOTOR_TEMP_CRIT,
        },
    })


# ─── Drive mode control ───────────────────────────────────────────────────────
@api_bp.route("/control/drive-mode", methods=["POST"])
def set_drive_mode():
    from backend.config import Config
    data = request.get_json(force=True)
    mode = data.get("mode", "NORMAL").upper()
    if mode not in Config.DRIVE_MODES:
        return jsonify({"error": f"Unknown mode '{mode}'"}), 400
    if _engine:
        _engine.drive_mode = mode
    return jsonify({"status": "ok", "drive_mode": mode})


# ─── Trip history ─────────────────────────────────────────────────────────────
@api_bp.route("/trips", methods=["GET"])
def list_trips():
    limit = int(request.args.get("limit", 20))
    return jsonify(get_trips(limit))


@api_bp.route("/trips/<int:trip_id>", methods=["GET"])
def trip_detail(trip_id):
    return jsonify(get_trip_detail(trip_id))


# ─── Alert history ────────────────────────────────────────────────────────────
@api_bp.route("/alerts/history", methods=["GET"])
def alert_history():
    if _engine is None:
        return jsonify([])
    limit = int(request.args.get("limit", 50))
    return jsonify(_engine.alerts.history(limit))


# ─── Health check ─────────────────────────────────────────────────────────────
@api_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "EV-Telemetry-Dashboard"})
