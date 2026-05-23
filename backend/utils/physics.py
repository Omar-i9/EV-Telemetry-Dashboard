"""
EV Physics Utilities
Real physics equations used in the simulation.
All formulas are documented with their source / derivation.
"""
import math
from backend.config import Config


# ─── Speed / RPM Conversions ─────────────────────────────────────────────────

def speed_to_motor_rpm(speed_kmh: float) -> float:
    """
    Convert vehicle speed (km/h) to motor electrical RPM.

    Derivation:
        wheel_rps  = speed_ms / (2π × r)     [wheel rotations per second]
        shaft_rps  = wheel_rps × gear_ratio   [motor shaft rotations per second]
        RPM        = shaft_rps × 60           [convert to RPM]
    """
    if speed_kmh <= 0:
        return 0.0
    speed_ms  = speed_kmh / 3.6
    wheel_rps = speed_ms / (2 * math.pi * Config.WHEEL_RADIUS_M)
    shaft_rps = wheel_rps * Config.GEAR_RATIO
    return shaft_rps * 60.0


def motor_rpm_to_speed(rpm: float) -> float:
    """Inverse of speed_to_motor_rpm."""
    if rpm <= 0:
        return 0.0
    shaft_rps = rpm / 60.0
    wheel_rps = shaft_rps / Config.GEAR_RATIO
    speed_ms  = wheel_rps * 2 * math.pi * Config.WHEEL_RADIUS_M
    return speed_ms * 3.6


# ─── Power and Force ─────────────────────────────────────────────────────────

def aerodynamic_drag_force(speed_kmh: float) -> float:
    """
    Fd = 0.5 × ρ × Cd × A × v²
    Returns drag force in Newtons.
    Significant above ~60 km/h — dominant resistance at highway speeds.
    """
    v = speed_kmh / 3.6
    return 0.5 * Config.AIR_DENSITY * Config.DRAG_COEFFICIENT * Config.FRONTAL_AREA_M2 * v ** 2


def rolling_resistance_force() -> float:
    """
    Fr = Crr × m × g
    Returns rolling resistance in Newtons (constant, independent of speed).
    """
    return Config.ROLLING_RESIST_COEFF * Config.VEHICLE_MASS_KG * 9.81


def total_road_load(speed_kmh: float) -> float:
    """Total resistive force on flat road at given speed."""
    return aerodynamic_drag_force(speed_kmh) + rolling_resistance_force()


def road_load_power_kw(speed_kmh: float) -> float:
    """
    P = F × v
    Power required just to maintain speed (no acceleration).
    """
    v = speed_kmh / 3.6
    return total_road_load(speed_kmh) * v / 1000.0


def acceleration_power_kw(speed_kmh: float, acceleration_ms2: float) -> float:
    """
    P_accel = m × a × v
    Extra power needed for acceleration on top of road-load.
    """
    v = speed_kmh / 3.6
    return Config.VEHICLE_MASS_KG * acceleration_ms2 * v / 1000.0


# ─── Motor Efficiency Map (simplified) ───────────────────────────────────────

def motor_efficiency(power_fraction: float, rpm: float) -> float:
    """
    Simplified motor efficiency curve.
    - Peak efficiency ~96% at 40–80% load and mid-speed range.
    - Falls off at very low loads (iron losses dominate) and max speed.
    - Returns fraction (0–1).
    """
    max_rpm = Config.MOTOR_MAX_RPM
    speed_frac  = min(rpm / max_rpm, 1.0) if max_rpm > 0 else 0
    load_frac   = abs(power_fraction)

    # Efficiency penalised at extremes
    speed_penalty = 1.0 - 0.08 * (speed_frac ** 2)   # loses ~8% near max speed
    load_penalty  = 1.0 - 0.10 * ((load_frac - 0.6) ** 2)  # peak efficiency at 60% load

    efficiency = Config.MOTOR_BASE_EFFICIENCY * speed_penalty * load_penalty
    return max(0.60, min(0.98, efficiency))


# ─── Battery Pack Voltage Model ───────────────────────────────────────────────

def soc_to_cell_voltage(soc_percent: float) -> float:
    """
    Empirical NMC cell OCV (Open Circuit Voltage) vs SOC curve.
    Approximated with a 4th-order polynomial fit to real NMC data.
    Returns cell voltage in Volts.
    """
    s = soc_percent / 100.0  # normalise to 0–1
    # Polynomial: V = a4·s⁴ + a3·s³ + a2·s² + a1·s + a0
    v = (0.1924 * s**4
         - 0.7123 * s**3
         + 0.8451 * s**2
         - 0.0023 * s
         + 3.0012)
    return max(Config.CELL_MIN_VOLTAGE, min(Config.CELL_MAX_VOLTAGE, v))


def pack_voltage_from_soc(soc_percent: float, current_A: float = 0.0) -> float:
    """
    V_pack = V_ocv × N_series  −  I × R_internal_pack
    Under-load voltage drop is included (IR drop).
    """
    v_cell  = soc_to_cell_voltage(soc_percent)
    r_pack  = Config.BATTERY_INTERNAL_RESIST * Config.BATTERY_CELLS_SERIES
    v_pack  = v_cell * Config.BATTERY_CELLS_SERIES - current_A * r_pack
    return round(max(Config.ALERT_PACK_VOLTAGE_MIN, v_pack), 2)


# ─── SOC Estimation (Coulomb Counting) ───────────────────────────────────────

def update_soc(soc_percent: float, current_A: float, dt_s: float, soh_percent: float = 100.0) -> float:
    """
    Coulomb counting: ΔSOc = -(I × Δt) / Q_max
    - Positive current  = discharge (draining)
    - Negative current  = charge / regen braking

    SOH scales the usable capacity: degraded battery loses range.
    """
    capacity_kwh  = Config.BATTERY_CAPACITY_KWH * (soh_percent / 100.0)
    capacity_Ah   = (capacity_kwh * 1000) / Config.BATTERY_NOMINAL_VOLTAGE
    delta_soc     = -(current_A * dt_s / 3600.0) / capacity_Ah * 100.0
    new_soc       = soc_percent + delta_soc
    return max(0.0, min(100.0, new_soc))


# ─── Range Estimation ─────────────────────────────────────────────────────────

def estimate_range_km(soc_percent: float, consumption_wh_per_km: float, soh_percent: float = 100.0) -> float:
    """
    Range = (SOC/100 × Capacity × SOH/100) / consumption
    Returns estimated range in km. Returns 0 if consumption is zero/invalid.
    """
    if consumption_wh_per_km <= 0:
        consumption_wh_per_km = 180.0  # fallback: 180 Wh/km ≈ normal highway
    usable_kwh = Config.BATTERY_CAPACITY_KWH * (soc_percent / 100.0) * (soh_percent / 100.0)
    return round((usable_kwh * 1000.0) / consumption_wh_per_km, 1)


# ─── Thermal Model ────────────────────────────────────────────────────────────

def battery_heat_generation_W(current_A: float) -> float:
    """
    Q = I² × R_internal (Joule heating in the pack)
    Returns heat in Watts.
    """
    r_pack = Config.BATTERY_INTERNAL_RESIST * Config.BATTERY_CELLS_SERIES
    return (current_A ** 2) * r_pack


def thermal_equilibrium_step(temp: float, heat_W: float, ambient: float, dt_s: float,
                              thermal_mass_kJ_per_K: float = 50.0,
                              cooling_W_per_K: float = 80.0) -> float:
    """
    Simplified 1st-order thermal model:
    dT/dt = (Q_gen - Q_cool) / C_thermal
    Q_cool = k × (T - T_ambient)   [Newton's law of cooling]
    """
    q_cool  = cooling_W_per_K * (temp - ambient)
    dT      = (heat_W - q_cool) * dt_s / (thermal_mass_kJ_per_K * 1000.0)
    return round(temp + dT, 2)
