"""
EV Telemetry Dashboard — Configuration
All vehicle parameters, thresholds, and application settings live here.
Changing a value here propagates everywhere automatically.
"""
import os

class Config:
    # ─── Flask ────────────────────────────────────────────────
    SECRET_KEY = os.environ.get("SECRET_KEY", "ev-telemetry-dev-secret")
    DEBUG      = os.environ.get("DEBUG", "true").lower() == "true"
    HOST       = os.environ.get("HOST", "0.0.0.0")
    PORT       = int(os.environ.get("PORT", 5000))

    # ─── Database ─────────────────────────────────────────────
    DATABASE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "telemetry.db")

    # ─── Battery Pack ─────────────────────────────────────────
    # 75 kWh pack — similar to Tesla Model 3 Long Range
    BATTERY_CAPACITY_KWH      = 75.0          # total usable kWh
    BATTERY_NOMINAL_VOLTAGE   = 400.0         # nominal pack voltage (V)
    BATTERY_CELLS_SERIES      = 96            # cells in series per module
    BATTERY_CELLS_PARALLEL    = 4             # parallel cell groups
    CELL_NOMINAL_VOLTAGE      = 3.65          # V — NMC chemistry
    CELL_MAX_VOLTAGE          = 4.20          # V — 100% SOC
    CELL_MIN_VOLTAGE          = 3.00          # V — 0% SOC
    BATTERY_INTERNAL_RESIST   = 0.0015        # Ω per cell
    BATTERY_INITIAL_SOC       = 85.0          # % starting charge
    BATTERY_INITIAL_SOH       = 98.0          # % state of health (capacity degradation)

    # ─── Motor / Drivetrain ───────────────────────────────────
    MOTOR_MAX_POWER_KW        = 250.0         # kW peak
    MOTOR_CONTINUOUS_POWER_KW = 180.0         # kW continuous
    MOTOR_MAX_TORQUE_NM       = 450.0         # Nm
    MOTOR_MAX_RPM             = 16_000        # max electrical RPM
    MOTOR_POLE_PAIRS          = 4             # affects RPM-speed relationship
    MOTOR_BASE_EFFICIENCY     = 0.96          # peak efficiency at rated load

    # ─── Vehicle Dynamics ─────────────────────────────────────
    VEHICLE_MASS_KG           = 2100          # kg (including battery ~500 kg)
    WHEEL_RADIUS_M            = 0.335         # m
    GEAR_RATIO                = 9.73          # single-speed reducer
    DRAG_COEFFICIENT          = 0.23          # Cd (aerodynamic)
    FRONTAL_AREA_M2           = 2.22          # m²
    ROLLING_RESIST_COEFF      = 0.010         # Crr (tyre rolling resistance)
    AIR_DENSITY               = 1.225         # kg/m³ at sea level

    # ─── Thermal ──────────────────────────────────────────────
    COOLANT_NOMINAL_TEMP      = 35.0          # °C normal coolant temp
    AMBIENT_TEMP              = 22.0          # °C ambient (can be variable)
    HVAC_MAX_POWER_KW         = 6.0           # kW max HVAC load

    # ─── WebSocket ────────────────────────────────────────────
    WS_EMIT_INTERVAL_S        = 0.5           # seconds between telemetry pushes

    # ─── Alert Thresholds ─────────────────────────────────────
    ALERT_SOC_LOW             = 20.0          # %
    ALERT_SOC_CRITICAL        = 10.0          # %
    ALERT_BATTERY_TEMP_WARN   = 42.0          # °C
    ALERT_BATTERY_TEMP_CRIT   = 55.0          # °C
    ALERT_MOTOR_TEMP_WARN     = 95.0          # °C
    ALERT_MOTOR_TEMP_CRIT     = 120.0         # °C
    ALERT_CELL_VOLTAGE_HIGH   = 4.15          # V
    ALERT_CELL_VOLTAGE_LOW    = 3.10          # V
    ALERT_CELL_IMBALANCE_MV   = 50            # mV max spread
    ALERT_DISCHARGE_CURR_MAX  = 350.0         # A
    ALERT_CHARGE_CURR_MAX     = 150.0         # A
    ALERT_PACK_VOLTAGE_MAX    = 420.0         # V
    ALERT_PACK_VOLTAGE_MIN    = 310.0         # V
    ALERT_COOLANT_TEMP_HIGH   = 80.0          # °C

    # ─── Fault Codes ──────────────────────────────────────────
    FAULT_CODES = {
        "P0A00": "Battery System Fault",
        "P0A01": "Cell Voltage Too High",
        "P0A02": "Cell Voltage Too Low",
        "P0A0F": "Battery Temperature Too High",
        "P0A80": "Battery Pack Deterioration",
        "P0AC0": "Motor Control System Fault",
        "P0B00": "High Voltage System Fault",
        "P1F00": "Thermal Management Fault",
        "P1F01": "Coolant Pump Fault",
        "P1F10": "HVAC System Fault",
    }

    # ─── Drive Modes ──────────────────────────────────────────
    DRIVE_MODES = {
        "ECO":    {"power_limit": 0.60, "regen_strength": 0.80, "torque_response": 0.70},
        "NORMAL": {"power_limit": 0.85, "regen_strength": 0.65, "torque_response": 0.85},
        "SPORT":  {"power_limit": 1.00, "regen_strength": 0.50, "torque_response": 1.00},
        "LUDICROUS": {"power_limit": 1.10, "regen_strength": 0.45, "torque_response": 1.10},
    }
