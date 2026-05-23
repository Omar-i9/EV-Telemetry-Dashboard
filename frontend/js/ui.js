/**
 * ui.js
 * The DOM layer — maps every field of the telemetry snapshot to its DOM element.
 * Keeps all document.getElementById calls in one place so app.js stays clean.
 *
 * Rule: this file NEVER talks to the server. It only reads from `data` and writes to DOM.
 */

'use strict';

// ── Cached DOM refs ──────────────────────────────────────────────────────────
const $  = (id) => document.getElementById(id);

const DOM = {
  // Speed
  speedValue:       $('speedValue'),
  maxSpeedVal:      $('maxSpeedVal'),
  avgSpeedVal:      $('avgSpeedVal'),
  driveModeVal:     $('driveModeVal'),
  // SOC
  socValue:         $('socValue'),
  rangeValue:       $('rangeValue'),
  socBar:           $('socBar'),
  sohValue:         $('sohValue'),
  regenPct:         $('regenPct'),
  energyConsumed:   $('energyConsumed'),
  // Power
  powerValue:       $('powerValue'),
  powerDir:         $('powerDir'),
  motorPBar:        $('motorPBar'),
  hvacPBar:         $('hvacPBar'),
  regenPBar:        $('regenPBar'),
  motorPVal:        $('motorPVal'),
  hvacPVal:         $('hvacPVal'),
  regenPVal:        $('regenPVal'),
  consumptionVal:   $('consumptionVal'),
  // Battery detail
  packVoltage:      $('packVoltage'),
  packCurrent:      $('packCurrent'),
  cellVMax:         $('cellVMax'),
  cellVMin:         $('cellVMin'),
  cellImbalance:    $('cellImbalance'),
  battTemp:         $('battTemp'),
  maxCellTemp:      $('maxCellTemp'),
  energyRegen:      $('energyRegen'),
  // Motor detail
  motorRpm:         $('motorRpm'),
  motorTorque:      $('motorTorque'),
  motorPowerDetail: $('motorPowerDetail'),
  motorEff:         $('motorEff'),
  motorTemp:        $('motorTemp'),
  regenActive:      $('regenActive'),
  rpmFill:          $('rpmFill'),
  rpmBarVal:        $('rpmBarVal'),
  // Thermal / GPS
  coolantTemp:      $('coolantTemp'),
  ambientTemp:      $('ambientTemp'),
  hvacLoad:         $('hvacLoad'),
  gpsLat:           $('gpsLat'),
  gpsLon:           $('gpsLon'),
  gpsHeading:       $('gpsHeading'),
  gpsAlt:           $('gpsAlt'),
  scenarioBadge:    $('scenarioBadge'),
  // Trip stats
  tripDist:         $('tripDist'),
  tripTime:         $('tripTime'),
  tripAvgSpeed:     $('tripAvgSpeed'),
  tripConsumption:  $('tripConsumption'),
  // Alerts
  alertsList:       $('alertsList'),
  alertCount:       $('alertCount'),
  tickerText:       $('tickerText'),
  // Timestamp
  timestamp:        $('timestamp'),
};

// ── Internal state ────────────────────────────────────────────────────────────
let _maxSpeed = 0;

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Clamp a value 0–1 and return it as a CSS percentage string. */
function pct(value, min, max) {
  return (Math.max(0, Math.min(1, (value - min) / (max - min))) * 100).toFixed(1) + '%';
}

/** Format seconds as MM:SS */
function formatTime(s) {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
}

/** Set a detail-item value with optional warn/crit colouring. */
function setVal(el, text, warn = false, crit = false) {
  if (!el) return;
  el.textContent = text;
  el.classList.toggle('warn', warn && !crit);
  el.classList.toggle('crit', crit);
}

// ── Main update function (called by socket_client.js) ─────────────────────────
window.updateDashboard = function(data) {
  const { battery, motor, vehicle, thermal, gps, alerts } = data;

  // ── Timestamp ─────────────────────────────────────────────
  if (DOM.timestamp) {
    DOM.timestamp.textContent = new Date(data.ts * 1000).toLocaleTimeString();
  }

  // ── Speed ─────────────────────────────────────────────────
  const speed = vehicle.speed_kmh;
  if (speed > _maxSpeed) _maxSpeed = speed;

  if (DOM.speedValue) DOM.speedValue.textContent = Math.round(speed);
  if (DOM.maxSpeedVal) DOM.maxSpeedVal.textContent = Math.round(_maxSpeed);
  if (DOM.avgSpeedVal) DOM.avgSpeedVal.textContent = Math.round(vehicle.avg_speed_kmh);

  // Redraw arc gauge
  const speedCanvas = document.getElementById('speedGauge');
  if (speedCanvas) {
    // Colour shifts amber at 140, red at 180
    let gaugeColor = '#00d4ff';
    if (speed > 180) gaugeColor = '#ff3355';
    else if (speed > 140) gaugeColor = '#ffaa00';
    drawArcGauge(speedCanvas, speed, 220, gaugeColor);
  }

  // ── Drive mode badge ──────────────────────────────────────
  if (DOM.driveModeVal) {
    DOM.driveModeVal.textContent = motor.drive_mode;
    DOM.driveModeVal.className   = `stat-mini__val drive-mode-badge ${motor.drive_mode}`;
  }

  // ── SOC ───────────────────────────────────────────────────
  const soc = battery.soc;
  if (DOM.socValue) DOM.socValue.textContent = soc.toFixed(1);
  if (DOM.rangeValue) DOM.rangeValue.textContent = vehicle.range_km;
  if (DOM.socBar) DOM.socBar.style.width = soc.toFixed(1) + '%';
  if (DOM.sohValue) DOM.sohValue.textContent = battery.soh.toFixed(1) + '%';
  if (DOM.regenPct) DOM.regenPct.textContent = battery.regen_percent.toFixed(1) + '%';
  if (DOM.energyConsumed) DOM.energyConsumed.textContent = battery.energy_discharged_kwh.toFixed(2) + ' kWh';

  // SOC ring canvas
  const socCanvas = document.getElementById('socRing');
  if (socCanvas) drawSOCRing(socCanvas, soc);

  // ── Power flow ────────────────────────────────────────────
  const motorPow   = Math.abs(motor.power_kw);
  const maxPow     = 250;   // kW — motor peak
  const hvacPow    = thermal.hvac_power_kw;
  const isRegen    = motor.regen_active;

  const totalPow   = isRegen ? -motorPow : motorPow;

  if (DOM.powerValue) DOM.powerValue.textContent = Math.abs(totalPow).toFixed(1);
  if (DOM.powerDir) {
    if (isRegen) {
      DOM.powerDir.textContent = '↑ REGEN';
      DOM.powerDir.className   = 'power-dir regen';
    } else if (speed < 2) {
      DOM.powerDir.textContent = 'IDLE';
      DOM.powerDir.className   = 'power-dir idle';
    } else {
      DOM.powerDir.textContent = '↓ DRIVE';
      DOM.powerDir.className   = 'power-dir';
    }
  }

  if (DOM.motorPBar)  DOM.motorPBar.style.width  = pct(motorPow, 0, maxPow);
  if (DOM.hvacPBar)   DOM.hvacPBar.style.width   = pct(hvacPow,  0, 6);
  if (DOM.regenPBar)  DOM.regenPBar.style.width  = isRegen ? pct(motorPow, 0, 100) : '0%';
  if (DOM.motorPVal)  DOM.motorPVal.textContent   = motorPow.toFixed(1) + ' kW';
  if (DOM.hvacPVal)   DOM.hvacPVal.textContent    = hvacPow.toFixed(1) + ' kW';
  if (DOM.regenPVal)  DOM.regenPVal.textContent   = isRegen ? motorPow.toFixed(1) + ' kW' : '0 kW';
  if (DOM.consumptionVal) DOM.consumptionVal.textContent = vehicle.consumption_wh_km.toFixed(0) + ' Wh/km';

  // ── Battery detail ────────────────────────────────────────
  const battTempWarn = battery.temperature >= 42;
  const battTempCrit = battery.temperature >= 55;

  setVal(DOM.packVoltage,  battery.pack_voltage.toFixed(1) + ' V');
  setVal(DOM.packCurrent,  battery.current.toFixed(1) + ' A',
         Math.abs(battery.current) > 250, Math.abs(battery.current) > 350);
  setVal(DOM.cellVMax,     battery.max_cell_voltage.toFixed(4) + ' V',
         battery.max_cell_voltage > 4.15);
  setVal(DOM.cellVMin,     battery.min_cell_voltage.toFixed(4) + ' V',
         battery.min_cell_voltage < 3.15, battery.min_cell_voltage < 3.0);
  setVal(DOM.cellImbalance, battery.cell_imbalance_mv.toFixed(1) + ' mV',
         battery.cell_imbalance_mv > 30, battery.cell_imbalance_mv > 50);
  setVal(DOM.battTemp,     battery.temperature.toFixed(1) + ' °C', battTempWarn, battTempCrit);
  setVal(DOM.maxCellTemp,  battery.max_cell_temp.toFixed(1) + ' °C', battTempWarn, battTempCrit);
  setVal(DOM.energyRegen,  battery.energy_recovered_kwh.toFixed(3) + ' kWh');

  // ── Motor detail ──────────────────────────────────────────
  const motorTempWarn = motor.temperature >= 95;
  const motorTempCrit = motor.temperature >= 120;
  const rpmPct        = (motor.rpm / 16000) * 100;

  setVal(DOM.motorRpm,         Math.round(motor.rpm) + ' rpm');
  setVal(DOM.motorTorque,      motor.torque_nm.toFixed(1) + ' Nm');
  setVal(DOM.motorPowerDetail, motor.power_kw.toFixed(1) + ' kW');
  setVal(DOM.motorEff,         motor.efficiency.toFixed(1) + ' %',
         motor.efficiency < 85, motor.efficiency < 70);
  setVal(DOM.motorTemp,        motor.temperature.toFixed(1) + ' °C', motorTempWarn, motorTempCrit);

  if (DOM.regenActive) {
    DOM.regenActive.textContent = motor.regen_active ? '✓ YES' : 'NO';
    DOM.regenActive.style.color = motor.regen_active ? '#00ff88' : '#6a8aaa';
  }

  if (DOM.rpmFill)   DOM.rpmFill.style.width  = rpmPct.toFixed(1) + '%';
  if (DOM.rpmBarVal) DOM.rpmBarVal.textContent = Math.round(motor.rpm) + ' rpm';

  // ── Thermal + GPS ─────────────────────────────────────────
  setVal(DOM.coolantTemp,  thermal.coolant_temp.toFixed(1) + ' °C',
         thermal.coolant_temp > 70, thermal.coolant_temp > 80);
  setVal(DOM.ambientTemp,  thermal.ambient_temp.toFixed(1) + ' °C');
  setVal(DOM.hvacLoad,     thermal.hvac_power_kw.toFixed(2) + ' kW');
  if (DOM.gpsLat)     DOM.gpsLat.textContent     = gps.latitude.toFixed(6);
  if (DOM.gpsLon)     DOM.gpsLon.textContent     = gps.longitude.toFixed(6);
  if (DOM.gpsHeading) DOM.gpsHeading.textContent = gps.heading_deg.toFixed(1) + '°';
  if (DOM.gpsAlt)     DOM.gpsAlt.textContent     = gps.altitude_m.toFixed(0) + ' m';
  if (DOM.scenarioBadge) DOM.scenarioBadge.textContent = vehicle.scenario;

  // ── Trip stats ────────────────────────────────────────────
  if (DOM.tripDist)        DOM.tripDist.textContent        = vehicle.trip_distance_km.toFixed(2);
  if (DOM.tripTime)        DOM.tripTime.textContent        = formatTime(vehicle.trip_time_s);
  if (DOM.tripAvgSpeed)    DOM.tripAvgSpeed.textContent    = Math.round(vehicle.avg_speed_kmh);
  if (DOM.tripConsumption) DOM.tripConsumption.textContent = vehicle.consumption_wh_km.toFixed(0);

  // ── Alerts ────────────────────────────────────────────────
  updateAlerts(alerts);

  // ── Push to streaming charts ──────────────────────────────
  if (window.CHARTS && window.pushChartPoint) {
    pushChartPoint(CHARTS.voltCurr, 0, battery.pack_voltage);
    pushChartPoint(CHARTS.voltCurr, 1, battery.current);
    pushChartPoint(CHARTS.temp,     0, battery.temperature);
    pushChartPoint(CHARTS.temp,     1, motor.temperature);
    pushChartPoint(CHARTS.temp,     2, thermal.coolant_temp);
  }
};

// ── Alert list renderer ───────────────────────────────────────────────────────
function updateAlerts(alerts) {
  if (!DOM.alertsList) return;

  // Update ticker
  if (DOM.tickerText) {
    if (!alerts || alerts.length === 0) {
      DOM.tickerText.textContent = 'ALL SYSTEMS NOMINAL';
      DOM.tickerText.className   = 'ticker-text';
    } else {
      // Show highest severity alert in ticker
      const top = alerts[0];
      DOM.tickerText.textContent = `[${top.code}] ${top.message}`;
      DOM.tickerText.className   = `ticker-text ${top.severity === 'CRITICAL' || top.severity === 'FAULT' ? 'crit' : 'warn'}`;
    }
  }

  if (DOM.alertCount) {
    DOM.alertCount.textContent = alerts.length;
    DOM.alertCount.classList.toggle('has-alerts', alerts.length > 0);
  }

  if (!alerts || alerts.length === 0) {
    DOM.alertsList.innerHTML = '<div class="alert-empty">All systems nominal</div>';
    return;
  }

  DOM.alertsList.innerHTML = alerts.map(a => `
    <div class="alert-item ${a.severity}">
      <span class="alert-sev">${a.severity}</span>
      <span class="alert-msg">${a.message}</span>
      <span class="alert-val">${a.value != null ? a.value + ' ' + a.unit : ''}</span>
    </div>
  `).join('');
}

// ── Drive mode button sync ─────────────────────────────────────────────────────
window.onDriveModeChanged = function(mode) {
  document.querySelectorAll('.dm-btn').forEach(btn => {
    btn.classList.toggle('dm-btn--active', btn.dataset.mode === mode);
  });
};
