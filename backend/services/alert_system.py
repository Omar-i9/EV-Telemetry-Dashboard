"""
Alert System
Monitors all telemetry values against configured thresholds.
Produces a live list of active alerts and a time-stamped history.
Severity levels: INFO, WARNING, CRITICAL, FAULT
"""
import time
from collections import deque
from backend.config import Config


SEVERITY_RANK = {"INFO": 0, "WARNING": 1, "CRITICAL": 2, "FAULT": 3}


class Alert:
    def __init__(self, code: str, message: str, severity: str, value=None, unit: str = ""):
        self.code      = code
        self.message   = message
        self.severity  = severity
        self.value     = value
        self.unit      = unit
        self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {
            "code":      self.code,
            "message":   self.message,
            "severity":  self.severity,
            "value":     round(self.value, 2) if isinstance(self.value, float) else self.value,
            "unit":      self.unit,
            "timestamp": round(self.timestamp, 2),
        }


class AlertSystem:
    """
    Stateless check engine — call evaluate() every tick with the latest
    telemetry snapshot. Returns the current active alert list.
    Historical alerts are kept in a fixed-size deque (last 200 events).
    """
    def __init__(self, history_size: int = 200):
        self._active:  list[Alert]            = []
        self._history: deque[Alert]           = deque(maxlen=history_size)
        self._seen_codes: set[str]            = set()   # avoid repeating same alert

    # ── Public API ───────────────────────────────────────────────────────────

    def evaluate(self, battery: dict, motor: dict, vehicle: dict, thermal: dict) -> list[dict]:
        """
        Run all checks, update active alerts, return current list as dicts.
        Alerts auto-clear when the condition resolves.
        """
        new_alerts: list[Alert] = []

        # ── Battery Checks ────────────────────────────────────
        new_alerts += self._check_soc(battery["soc"])
        new_alerts += self._check_pack_voltage(battery["pack_voltage"])
        new_alerts += self._check_cell_voltage(battery["min_cell_voltage"], battery["max_cell_voltage"])
        new_alerts += self._check_battery_temp(battery["temperature"])
        new_alerts += self._check_cell_imbalance(battery["cell_imbalance_mv"])
        new_alerts += self._check_current(battery["current"])
        new_alerts += self._check_soh(battery["soh"])

        # ── Motor Checks ──────────────────────────────────────
        new_alerts += self._check_motor_temp(motor["temperature"])
        new_alerts += self._check_motor_efficiency(motor["efficiency"])

        # ── Thermal Checks ────────────────────────────────────
        new_alerts += self._check_coolant(thermal["coolant_temp"])

        # ── Vehicle Checks ────────────────────────────────────
        new_alerts += self._check_speed(vehicle["speed_kmh"])

        # ── Update state ──────────────────────────────────────
        # Add new alerts that weren't already active
        active_codes = {a.code for a in self._active}
        for alert in new_alerts:
            if alert.code not in active_codes:
                self._history.append(alert)
        self._active = new_alerts  # replace entire list each tick

        return [a.to_dict() for a in sorted(self._active,
                key=lambda a: SEVERITY_RANK[a.severity], reverse=True)]

    def history(self, limit: int = 50) -> list[dict]:
        return [a.to_dict() for a in list(self._history)[-limit:]]

    # ── Check Methods ─────────────────────────────────────────────────────────

    def _check_soc(self, soc: float) -> list[Alert]:
        if soc <= Config.ALERT_SOC_CRITICAL:
            return [Alert("SOC_CRIT", "CRITICAL — Battery charge critically low", "CRITICAL", soc, "%")]
        if soc <= Config.ALERT_SOC_LOW:
            return [Alert("SOC_LOW", "Battery charge low — find a charger", "WARNING", soc, "%")]
        return []

    def _check_pack_voltage(self, v: float) -> list[Alert]:
        if v > Config.ALERT_PACK_VOLTAGE_MAX:
            return [Alert("VOLT_HIGH", "Pack voltage above safe limit", "CRITICAL", v, "V")]
        if v < Config.ALERT_PACK_VOLTAGE_MIN:
            return [Alert("VOLT_LOW", "Pack voltage below minimum threshold", "FAULT", v, "V")]
        return []

    def _check_cell_voltage(self, v_min: float, v_max: float) -> list[Alert]:
        alerts = []
        if v_max > Config.ALERT_CELL_VOLTAGE_HIGH:
            alerts.append(Alert("CELL_V_HIGH", "Cell over-voltage detected", "WARNING", v_max, "V/cell"))
        if v_min < Config.ALERT_CELL_VOLTAGE_LOW:
            alerts.append(Alert("CELL_V_LOW", "Cell under-voltage detected", "CRITICAL", v_min, "V/cell"))
        return alerts

    def _check_battery_temp(self, temp: float) -> list[Alert]:
        if temp >= Config.ALERT_BATTERY_TEMP_CRIT:
            return [Alert("BATT_TEMP_CRIT", "Battery overheating — reduce power", "CRITICAL", temp, "°C")]
        if temp >= Config.ALERT_BATTERY_TEMP_WARN:
            return [Alert("BATT_TEMP_WARN", "Battery temperature elevated", "WARNING", temp, "°C")]
        return []

    def _check_cell_imbalance(self, imbalance_mv: float) -> list[Alert]:
        if imbalance_mv > Config.ALERT_CELL_IMBALANCE_MV:
            return [Alert("CELL_IMBAL", "Cell voltage imbalance detected — check BMS", "WARNING",
                          imbalance_mv, "mV")]
        return []

    def _check_current(self, current: float) -> list[Alert]:
        alerts = []
        if current > Config.ALERT_DISCHARGE_CURR_MAX:
            alerts.append(Alert("CURR_HIGH", "Discharge current exceeds safe limit", "CRITICAL", current, "A"))
        if current < -Config.ALERT_CHARGE_CURR_MAX:
            alerts.append(Alert("REGEN_HIGH", "Regenerative current too high", "WARNING", abs(current), "A"))
        return alerts

    def _check_soh(self, soh: float) -> list[Alert]:
        if soh < 85.0:
            return [Alert("SOH_LOW", "Battery health degraded — consider replacement", "INFO", soh, "%")]
        return []

    def _check_motor_temp(self, temp: float) -> list[Alert]:
        if temp >= Config.ALERT_MOTOR_TEMP_CRIT:
            return [Alert("MOTOR_TEMP_CRIT", "Motor overheating — power reduced", "CRITICAL", temp, "°C")]
        if temp >= Config.ALERT_MOTOR_TEMP_WARN:
            return [Alert("MOTOR_TEMP_WARN", "Motor temperature elevated", "WARNING", temp, "°C")]
        return []

    def _check_motor_efficiency(self, eff_pct: float) -> list[Alert]:
        if eff_pct < 70.0:
            return [Alert("MOTOR_EFF", "Motor efficiency unusually low", "INFO", eff_pct, "%")]
        return []

    def _check_coolant(self, temp: float) -> list[Alert]:
        if temp > Config.ALERT_COOLANT_TEMP_HIGH:
            return [Alert("COOLANT_HIGH", "Coolant temperature too high", "CRITICAL", temp, "°C")]
        return []

    def _check_speed(self, speed: float) -> list[Alert]:
        if speed > 250.0:
            return [Alert("SPEED_LIMIT", "Vehicle speed exceeds safe simulation range", "INFO", speed, "km/h")]
        return []
