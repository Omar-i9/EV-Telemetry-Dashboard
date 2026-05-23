"""
Telemetry Engine
The brain of the simulation. Orchestrates BatteryModel, MotorModel, AlertSystem,
and produces one unified telemetry snapshot every tick.

Driving scenarios cycle automatically so the dashboard always has interesting data:
  IDLE → ACCELERATING → CRUISING → REGEN_BRAKING → CRUISING → ...
"""
import time
import math
import random
from backend.config import Config
from backend.services.battery_model import BatteryModel
from backend.services.motor_model   import MotorModel
from backend.services.alert_system  import AlertSystem
from backend.utils.physics import (
    road_load_power_kw, estimate_range_km
)


# ─── Driving Scenario Definitions ────────────────────────────────────────────

SCENARIOS = [
    # (name, duration_s, target_speed_kmh, acceleration_ms2, drive_mode)
    ("IDLE",          8,  0,    0.0,   "NORMAL"),
    ("ACCELERATING",  12, 60,   2.5,   "SPORT"),
    ("CRUISING",      20, 60,   0.0,   "NORMAL"),
    ("ACCELERATING",  10, 110,  2.0,   "SPORT"),
    ("CRUISING",      25, 110,  0.0,   "NORMAL"),
    ("REGEN_BRAKING", 10, 60,  -2.5,   "NORMAL"),
    ("CRUISING",      15, 60,   0.0,   "ECO"),
    ("REGEN_BRAKING",  8, 20,  -3.0,   "NORMAL"),
    ("IDLE",           6,  0,   0.0,   "NORMAL"),
    ("ACCELERATING",  14, 90,   1.8,   "LUDICROUS"),
    ("CRUISING",      20, 90,   0.0,   "NORMAL"),
    ("REGEN_BRAKING", 12, 30,  -2.0,   "ECO"),
]


class TelemetryEngine:
    """
    Tick-driven simulation engine.
    Call `snapshot()` to get the current unified telemetry dict.
    The engine internally advances its own state each call.
    """

    def __init__(self):
        self.battery        = BatteryModel()
        self.motor          = MotorModel()
        self.alerts         = AlertSystem()

        # ── Vehicle state ─────────────────────────────────────
        self.speed_kmh      = 0.0
        self.acceleration   = 0.0
        self.drive_mode     = "NORMAL"
        self.odometer_km    = 0.0
        self.trip_distance  = 0.0
        self.trip_start     = time.time()

        # ── Thermal / HVAC ────────────────────────────────────
        self.coolant_temp   = 35.0       # °C
        self.ambient_temp   = Config.AMBIENT_TEMP
        self.hvac_power_kw  = 2.5        # kW (AC running)

        # ── GPS simulation (circular track mock) ──────────────
        self._gps_angle     = 0.0        # degrees, advances with speed
        self._gps_lat_base  = 31.7683    # somewhere nice (Jerusalem area)
        self._gps_lon_base  = 35.2137
        self._gps_radius    = 0.005      # ~500 m radius

        # ── Scenario management ───────────────────────────────
        self._scenario_idx  = 0
        self._scenario_start= time.time()

        # ── Energy accounting ─────────────────────────────────
        self._consumption_window: list[float] = []   # recent Wh/km values
        self._last_tick     = time.time()

    # ── Main interface ────────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        """Advance state and return complete telemetry snapshot."""
        self._advance_scenario()
        self._update_speed()
        self._update_thermal()
        self._update_gps()

        now = time.time()
        dt  = now - self._last_tick
        self._last_tick = now

        # ── Calculate current demand ──────────────────────────
        motor_power_kw = self._calculate_motor_power()
        # Convert motor power to battery current (including HVAC and accessories)
        accessory_kw   = self.hvac_power_kw + 0.5  # 0.5 kW misc electronics
        total_power_kw = motor_power_kw + accessory_kw
        battery_current = (total_power_kw * 1000.0) / max(self.battery.pack_voltage, 1.0)
        # Regen: current is negative when motor is generating
        if self.motor.regen_active:
            battery_current = -abs(battery_current) * 0.92  # regen efficiency

        # ── Update sub-models ─────────────────────────────────
        self.motor.update(self.speed_kmh, self.acceleration, self.drive_mode)
        self.battery.update(battery_current, self.drive_mode)

        # ── Odometer / distance ───────────────────────────────
        dist_this_tick = self.speed_kmh / 3600.0 * dt   # km
        self.odometer_km  += dist_this_tick
        self.trip_distance += dist_this_tick

        # ── Energy consumption ────────────────────────────────
        if dist_this_tick > 0:
            wh_this_tick = total_power_kw * 1000.0 * dt / 3600.0
            wh_per_km    = wh_this_tick / dist_this_tick
            self._consumption_window.append(wh_per_km)
            if len(self._consumption_window) > 60:    # ~30 s rolling average
                self._consumption_window.pop(0)
        avg_consumption = (
            sum(self._consumption_window) / len(self._consumption_window)
            if self._consumption_window else 180.0
        )

        # ── Estimated range ───────────────────────────────────
        range_km = estimate_range_km(self.battery.soc, avg_consumption, self.battery.soh)

        # ── Assemble vehicle sub-dict ─────────────────────────
        vehicle_dict = {
            "speed_kmh":         round(self.speed_kmh, 1),
            "acceleration_ms2":  round(self.acceleration, 2),
            "odometer_km":       round(self.odometer_km, 2),
            "trip_distance_km":  round(self.trip_distance, 2),
            "trip_time_s":       round(time.time() - self.trip_start, 0),
            "avg_speed_kmh":     self._avg_speed(),
            "range_km":          range_km,
            "consumption_wh_km": round(avg_consumption, 1),
            "scenario":          SCENARIOS[self._scenario_idx][0],
        }

        thermal_dict = {
            "coolant_temp":      round(self.coolant_temp, 1),
            "ambient_temp":      round(self.ambient_temp, 1),
            "hvac_power_kw":     round(self.hvac_power_kw, 2),
        }

        gps_dict = {
            "latitude":          round(self._gps_lat_base + self._gps_radius *
                                       math.sin(math.radians(self._gps_angle)), 6),
            "longitude":         round(self._gps_lon_base + self._gps_radius *
                                       math.cos(math.radians(self._gps_angle)), 6),
            "heading_deg":       round(self._gps_angle % 360, 1),
            "altitude_m":        round(800 + 20 * math.sin(math.radians(self._gps_angle * 2)), 1),
        }

        # ── Evaluate alerts ───────────────────────────────────
        active_alerts = self.alerts.evaluate(
            self.battery.to_dict(), self.motor.to_dict(), vehicle_dict, thermal_dict
        )

        return {
            "ts":        round(time.time(), 3),
            "battery":   self.battery.to_dict(),
            "motor":     self.motor.to_dict(),
            "vehicle":   vehicle_dict,
            "thermal":   thermal_dict,
            "gps":       gps_dict,
            "alerts":    active_alerts,
        }

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _advance_scenario(self) -> None:
        """Switch to the next driving scenario when the current one expires."""
        scenario = SCENARIOS[self._scenario_idx]
        elapsed  = time.time() - self._scenario_start
        if elapsed >= scenario[1]:
            self._scenario_idx   = (self._scenario_idx + 1) % len(SCENARIOS)
            self._scenario_start = time.time()

    def _update_speed(self) -> None:
        """Smoothly move speed toward the scenario target."""
        _, _, target_speed, target_acc, self.drive_mode = SCENARIOS[self._scenario_idx]

        # Apply drive-mode torque response factor to acceleration smoothness
        resp_factor  = Config.DRIVE_MODES[self.drive_mode]["torque_response"]
        max_accel    = abs(target_acc) * resp_factor
        dt = Config.WS_EMIT_INTERVAL_S

        diff = target_speed - self.speed_kmh
        if abs(diff) < 1.0:
            self.speed_kmh  = target_speed
            self.acceleration = 0.0
        else:
            # Acceleration in km/h per tick
            step = math.copysign(min(abs(diff), max_accel * dt * 3.6), diff)
            self.speed_kmh   = max(0.0, self.speed_kmh + step + random.gauss(0, 0.3))
            self.acceleration = target_acc + random.gauss(0, 0.05)

    def _calculate_motor_power(self) -> float:
        """Return the motor mechanical power demand in kW (positive = consume, negative = generate)."""
        from backend.utils.physics import road_load_power_kw, acceleration_power_kw
        p_road  = road_load_power_kw(self.speed_kmh)
        p_accel = acceleration_power_kw(self.speed_kmh, self.acceleration)
        power   = p_road + p_accel

        if self.acceleration < -0.1 and self.speed_kmh > 5.0:
            # Regen: recover a portion of kinetic energy
            regen_frac = Config.DRIVE_MODES[self.drive_mode]["regen_strength"]
            return -abs(power) * regen_frac
        return max(0.0, power)

    def _update_thermal(self) -> None:
        """Coolant temperature reacts to motor heat."""
        from backend.utils.physics import thermal_equilibrium_step
        motor_heat_W = abs(self.motor.power_kw) * 1000.0 * (1.0 - self.motor.efficiency / 100.0)
        self.coolant_temp = thermal_equilibrium_step(
            self.coolant_temp, motor_heat_W * 0.3,
            self.ambient_temp, Config.WS_EMIT_INTERVAL_S,
            thermal_mass_kJ_per_K=20.0, cooling_W_per_K=60.0
        )

    def _update_gps(self) -> None:
        """Advance GPS position along a circular mock track."""
        speed_ms = self.speed_kmh / 3.6
        circumference = 2 * math.pi * (self._gps_radius * 111_000)  # approx metres
        if circumference > 0:
            angular_speed_deg_per_s = (speed_ms / circumference) * 360.0
            self._gps_angle = (self._gps_angle + angular_speed_deg_per_s *
                               Config.WS_EMIT_INTERVAL_S) % 360.0

    def _avg_speed(self) -> float:
        elapsed = max(time.time() - self.trip_start, 1.0)
        return round((self.trip_distance / elapsed) * 3600.0, 1)
