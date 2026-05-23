# ⚡ EV Telemetry Dashboard

> Real-time electric vehicle telemetry system — battery physics, motor dynamics,
> thermal modelling, live WebSocket streaming, and a dark automotive HUD interface.

![Dashboard Preview](docs/preview.png)

---

## ✨ What This Project Does

This is a full-stack simulation dashboard for an electric vehicle. It doesn't just show random numbers — it runs a **physics-based simulation engine** on the backend that models:

- **Battery pack** — SOC via Coulomb Counting, cell voltage OCV curves, IR drop under load, Joule heating, state of health degradation
- **Motor / drivetrain** — RPM from wheel geometry, torque calculation, efficiency map, winding temperature
- **Thermal management** — 1st-order thermal model for battery and motor, coolant loop
- **Vehicle dynamics** — aerodynamic drag (Fd = ½ρCdAv²), rolling resistance, acceleration power demand
- **Regenerative braking** — proper energy recovery with efficiency factor
- **Alert system** — 15+ threshold checks with severities: INFO / WARNING / CRITICAL / FAULT
- **GPS simulation** — vehicle moves along a circular mock track

The frontend receives **live data every 500 ms via WebSocket** and renders streaming charts, arc gauges, and a full detail panel — no page refresh needed.

---

## 🗂️ Project Structure

```
EV-Telemetry-Dashboard/
│
├── run.py                        ← Entry point: python run.py
│
├── backend/
│   ├── app.py                    ← Flask app factory (wires everything)
│   ├── config.py                 ← All vehicle parameters and thresholds
│   ├── requirements.txt          ← Python dependencies
│   │
│   ├── models/
│   │   └── database.py           ← SQLite: trips, telemetry_log, fault_events
│   │
│   ├── services/
│   │   ├── telemetry_engine.py   ← Main simulation orchestrator
│   │   ├── battery_model.py      ← Battery state tracker (SOC, voltage, temp)
│   │   ├── motor_model.py        ← Motor RPM, torque, efficiency, temperature
│   │   └── alert_system.py       ← Threshold checks → Alert objects
│   │
│   ├── routes/
│   │   ├── api.py                ← REST endpoints (/api/...)
│   │   └── events.py             ← WebSocket events (Socket.IO)
│   │
│   └── utils/
│       └── physics.py            ← Pure physics equations (documented)
│
├── frontend/
│   ├── index.html                ← Dashboard layout (9-panel grid)
│   ├── css/
│   │   └── dashboard.css         ← Dark automotive HUD theme
│   └── js/
│       ├── app.js                ← Entry point: controls, keyboard shortcuts
│       ├── charts.js             ← Chart.js streaming charts + arc gauges
│       ├── socket_client.js      ← WebSocket client (Socket.IO)
│       └── ui.js                 ← Maps telemetry data → DOM elements
│
└── data/
    └── telemetry.db              ← SQLite database (auto-created on first run)
```

---

## 🚀 Getting Started

### 1. Clone or download the project

```bash
git clone https://github.com/yourname/EV-Telemetry-Dashboard.git
cd EV-Telemetry-Dashboard
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv

# On Windows:
venv\Scripts\activate

# On macOS / Linux:
source venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install -r backend/requirements.txt
```

### 4. Run the server

```bash
python run.py
```

### 5. Open the dashboard

Navigate to **http://localhost:5000** in your browser. You should see the dashboard immediately start receiving live data.

---

## 🔌 API Reference

All REST endpoints are prefixed with `/api`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/telemetry` | Current telemetry snapshot (HTTP fallback) |
| GET | `/api/config` | Vehicle configuration and thresholds |
| POST | `/api/control/drive-mode` | Set drive mode `{"mode": "SPORT"}` |
| GET | `/api/trips` | List past trips |
| GET | `/api/trips/:id` | Trip detail with logs and faults |
| GET | `/api/alerts/history` | Last 50 alert events |

### WebSocket Events

**Server → Client**

| Event | Payload | Description |
|-------|---------|-------------|
| `telemetry` | Full snapshot dict | Emitted every 500 ms |
| `config` | Vehicle config | Sent once on connect |
| `drive_mode_changed` | `{mode}` | Confirmed mode change |
| `trip_reset` | `{ts}` | Trip successfully reset |

**Client → Server**

| Event | Payload | Description |
|-------|---------|-------------|
| `set_drive_mode` | `{mode}` | Request drive mode change |
| `reset_trip` | — | Reset trip counters |
| `request_snapshot` | — | Get immediate snapshot |

---

## ⚙️ Configuration

All vehicle parameters live in `backend/config.py`. This is the **single source of truth** — changing a value here propagates to every simulation, alert threshold, and API response automatically.

Key parameters you'll want to adjust:

```python
BATTERY_CAPACITY_KWH   = 75.0   # Total pack size
MOTOR_MAX_POWER_KW     = 250.0  # Peak motor output
VEHICLE_MASS_KG        = 2100   # Affects drag and acceleration power
WS_EMIT_INTERVAL_S     = 0.5    # Telemetry frequency (seconds)
BATTERY_INITIAL_SOC    = 85.0   # Starting charge level (%)
```

---

## 🧪 Physics: How the Simulation Works

The simulation is not random noise — each value is derived from real engineering equations.

**SOC (State of Charge)** uses Coulomb Counting:
```
ΔSOC = -(I × Δt) / Q_max
```
Where `I` is pack current in Amperes, `Δt` is the timestep, and `Q_max` is total capacity in Ah, scaled by SOH.

**Pack voltage** uses an OCV (Open Circuit Voltage) curve fitted to real NMC cell data, plus an IR drop under load:
```
V_pack = V_ocv(SOC) × N_series - I × R_internal
```

**Motor RPM** is derived geometrically from wheel speed:
```
RPM = (speed_ms / (2π × r_wheel)) × gear_ratio × 60
```

**Road load power** combines aerodynamic drag and rolling resistance:
```
P_road = (½ρCdAv² + Crr×m×g) × v
```

**Thermal model** is a first-order Newton's law of cooling with Joule heating as the source:
```
dT/dt = (I²R - k×(T - T_ambient)) / C_thermal
```

---

## 🗺️ Roadmap (v2 and beyond)

These are the natural next steps for making this a production-grade project:

**Real-time improvements**
- Replace mock GPS with actual GPS coordinates from a file or device
- Add WebSocket compression for lower bandwidth
- Support multiple vehicle connections on one dashboard

**Data and analytics**
- Trip replay: scrub through recorded telemetry data
- Energy efficiency heatmap over a route
- Predictive range using rolling consumption + weather API

**Hardware integration**
- CAN bus bridge: read real OBD-II / CAN data from a vehicle
- MQTT support for IoT / edge deployments
- Raspberry Pi deployment guide

**Frontend**
- Dark/light theme toggle
- Export trip data as CSV
- Mobile-responsive full-screen mode

---

## 📦 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, Flask 3, Flask-SocketIO 5 |
| Real-time | WebSocket via Socket.IO |
| Database | SQLite (zero-config, file-based) |
| Frontend | Vanilla HTML5 / CSS3 / ES6+ |
| Charts | Chart.js 4 with streaming plugin |
| Fonts | Rajdhani + Share Tech Mono (Google Fonts) |

---

## 📝 Commit Message Convention

Follow this pattern to keep the git history professional:

```
feat: add regenerative braking energy counter
fix: correct SOC drift at low current values
style: improve mobile layout for battery panel
perf: reduce WebSocket payload size by 30%
docs: add physics equations to README
refactor: split telemetry_engine into sub-services
```

---

## 📄 License

MIT — free to use, modify, and distribute.
