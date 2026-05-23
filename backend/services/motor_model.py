"""
Motor / Drivetrain Model
Tracks motor RPM, torque, temperature, efficiency, and drive mode.
"""
import random
import time
from backend.config import Config
from backend.utils.physics import (
    speed_to_motor_rpm, motor_efficiency, thermal_equilibrium_step
)


class MotorModel:
    def __init__(self):
        self.rpm           = 0.0
        self.torque_nm     = 0.0
        self.power_kw      = 0.0
        self.efficiency    = 0.96
        self.temperature   = 35.0        # °C winding temperature
        self.drive_mode    = "NORMAL"
        self.regen_active  = False

        self._last_tick    = time.time()

    def update(self, speed_kmh: float, acceleration_ms2: float, drive_mode: str) -> None:
        now = time.time()
        dt  = now - self._last_tick
        self._last_tick = now

        self.drive_mode   = drive_mode
        mode_cfg          = Config.DRIVE_MODES[drive_mode]
        power_limit_frac  = mode_cfg["power_limit"]
        max_power_kw      = Config.MOTOR_MAX_POWER_KW * power_limit_frac

        # ── RPM ──────────────────────────────────────────────
        self.rpm = round(speed_to_motor_rpm(speed_kmh), 0)

        # ── Power demand from dynamics ────────────────────────
        from backend.utils.physics import road_load_power_kw, acceleration_power_kw
        p_road  = road_load_power_kw(speed_kmh)
        p_accel = acceleration_power_kw(speed_kmh, acceleration_ms2)
        raw_power = p_road + p_accel

        # ── Regen braking ────────────────────────────────────
        if acceleration_ms2 < -0.05 and speed_kmh > 5.0:
            self.regen_active = True
            regen_frac = mode_cfg["regen_strength"]
            # Regen power limited by motor and battery charge limits
            regen_power = min(abs(raw_power) * regen_frac, Config.MOTOR_CONTINUOUS_POWER_KW)
            self.power_kw = -round(regen_power, 2)
        else:
            self.regen_active = False
            # Clamp to drive-mode power limit
            self.power_kw = round(min(raw_power, max_power_kw), 2)

        # ── Torque ────────────────────────────────────────────
        if self.rpm > 0:
            # P = T × ω  →  T = P / ω  (ω in rad/s)
            omega_rad_s    = self.rpm * 2 * 3.14159 / 60.0
            shaft_power_W  = abs(self.power_kw) * 1000.0
            raw_torque     = shaft_power_W / omega_rad_s
            self.torque_nm = round(min(raw_torque, Config.MOTOR_MAX_TORQUE_NM), 1)
        else:
            self.torque_nm = 0.0

        # ── Efficiency ────────────────────────────────────────
        power_fraction    = abs(self.power_kw) / Config.MOTOR_MAX_POWER_KW
        self.efficiency   = round(motor_efficiency(power_fraction, self.rpm), 4)

        # ── Thermal ──────────────────────────────────────────
        heat_W = abs(self.power_kw) * 1000.0 * (1.0 - self.efficiency)
        self.temperature = thermal_equilibrium_step(
            self.temperature, heat_W, Config.AMBIENT_TEMP, dt,
            thermal_mass_kJ_per_K=8.0, cooling_W_per_K=120.0
        )
        self.temperature = round(self.temperature + random.gauss(0, 0.15), 1)

    def to_dict(self) -> dict:
        return {
            "rpm":          round(self.rpm, 0),
            "torque_nm":    self.torque_nm,
            "power_kw":     self.power_kw,
            "efficiency":   round(self.efficiency * 100.0, 1),
            "temperature":  self.temperature,
            "drive_mode":   self.drive_mode,
            "regen_active": self.regen_active,
        }
