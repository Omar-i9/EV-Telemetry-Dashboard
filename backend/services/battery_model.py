"""
Battery Model Service
Tracks the full battery pack state: SOC, voltage, current, temperature, SOH,
cell imbalance, and energy counters. All physics via utils/physics.py.
"""
import time
import random
import math
from backend.config import Config
from backend.utils.physics import (
    pack_voltage_from_soc, update_soc, soc_to_cell_voltage,
    battery_heat_generation_W, thermal_equilibrium_step
)


class BatteryModel:
    def __init__(self):
        self.soc              = Config.BATTERY_INITIAL_SOC          # %
        self.soh              = Config.BATTERY_INITIAL_SOH          # %
        self.pack_voltage     = pack_voltage_from_soc(self.soc)     # V
        self.current          = 0.0                                 # A (+ = discharge, - = regen)
        self.temperature      = 28.0                                # °C average cell temp
        self.max_cell_temp    = 30.0                                # °C hottest cell
        self.min_cell_voltage = soc_to_cell_voltage(self.soc)      # V
        self.max_cell_voltage = soc_to_cell_voltage(self.soc)      # V
        self.cell_imbalance_mV = 3.0                                # mV spread (healthy = <50 mV)

        self.energy_discharged_kWh = 0.0
        self.energy_recovered_kWh  = 0.0    # from regenerative braking
        self.total_charge_cycles   = 0.0    # accumulated partial cycles

        self._last_tick = time.time()

    def update(self, current_A: float, drive_mode: str = "NORMAL") -> None:
        """
        Advance the battery state by one simulation timestep.
        Called by TelemetryEngine every WS_EMIT_INTERVAL_S seconds.
        """
        now = time.time()
        dt  = now - self._last_tick
        self._last_tick = now

        self.current = current_A

        # ── SOC via Coulomb Counting ───────────────────────────
        self.soc = update_soc(self.soc, current_A, dt, self.soh)

        # ── Pack voltage (OCV + IR drop) ──────────────────────
        self.pack_voltage = pack_voltage_from_soc(self.soc, current_A)

        # ── Cell-level statistics (simulated spread) ──────────
        base_v = soc_to_cell_voltage(self.soc)
        # Healthy cells differ by a few mV, degraded cells by more
        imbalance_factor  = (100.0 - self.soh) / 100.0 * 30.0  # 0–30 mV extra with age
        self.cell_imbalance_mV = round(3.0 + imbalance_factor + random.gauss(0, 0.5), 1)
        self.min_cell_voltage  = round(base_v - self.cell_imbalance_mV / 2000.0, 4)
        self.max_cell_voltage  = round(base_v + self.cell_imbalance_mV / 2000.0, 4)

        # ── Thermal model ─────────────────────────────────────
        heat_W = battery_heat_generation_W(abs(current_A))
        self.temperature = thermal_equilibrium_step(
            self.temperature, heat_W, Config.AMBIENT_TEMP, dt,
            thermal_mass_kJ_per_K=60.0, cooling_W_per_K=90.0
        )
        # Hottest cell is slightly above average (non-uniform cooling)
        self.max_cell_temp = round(self.temperature + random.gauss(2.5, 0.3), 1)

        # ── Energy accounting ─────────────────────────────────
        power_kW = abs(self.pack_voltage * current_A) / 1000.0
        if current_A > 0:                             # discharging
            self.energy_discharged_kWh += power_kW * dt / 3600.0
        elif current_A < 0:                           # regenerating / charging
            self.energy_recovered_kWh  += power_kW * dt / 3600.0

        # ── Slow SOH degradation (simulated) ──────────────────
        # 0.0001% per cycle ≈ degrades ~1% per 10,000 cycles (realistic)
        self.total_charge_cycles += abs(current_A) * dt / 3600.0 / \
            ((Config.BATTERY_CAPACITY_KWH * 1000.0) / Config.BATTERY_NOMINAL_VOLTAGE)
        self.soh = max(80.0, Config.BATTERY_INITIAL_SOH - self.total_charge_cycles * 0.0001)

    def to_dict(self) -> dict:
        """Serialise to JSON-safe dict for API / WebSocket emission."""
        return {
            "soc":                  round(self.soc, 1),
            "soh":                  round(self.soh, 2),
            "pack_voltage":         round(self.pack_voltage, 1),
            "current":              round(self.current, 1),
            "power_kw":             round(self.pack_voltage * self.current / 1000.0, 2),
            "temperature":          round(self.temperature, 1),
            "max_cell_temp":        round(self.max_cell_temp, 1),
            "min_cell_voltage":     round(self.min_cell_voltage, 4),
            "max_cell_voltage":     round(self.max_cell_voltage, 4),
            "cell_imbalance_mv":    round(self.cell_imbalance_mV, 1),
            "energy_discharged_kwh":round(self.energy_discharged_kWh, 3),
            "energy_recovered_kwh": round(self.energy_recovered_kWh, 3),
            "regen_percent": round(
                self.energy_recovered_kWh /
                max(self.energy_discharged_kWh + self.energy_recovered_kWh, 0.001) * 100.0, 1
            ),
        }
