/**
 * charts.js
 * Initialises all Chart.js instances used by the dashboard.
 * Each chart is exported on the global `CHARTS` object so ui.js can push data.
 *
 * Design decisions:
 *  - Streaming plugin used for voltage/current/temp (real-time sliding window)
 *  - Doughnut canvases drawn manually via Canvas API for speed/SOC gauges
 *    (Chart.js doughnut would work but custom canvas gives us more control)
 */

'use strict';

window.CHARTS = {};

// ─── Colour tokens (mirror CSS variables) ────────────────────────────────────
const C = {
  cyan:    '#00d4ff',
  green:   '#00ff88',
  amber:   '#ffaa00',
  red:     '#ff3355',
  purple:  '#bf5fff',
  dimLine: '#1c2a38',
  bg:      '#0d1117',
};

// ─── Shared streaming chart defaults ─────────────────────────────────────────
Chart.defaults.color        = '#6a8aaa';
Chart.defaults.borderColor  = '#1c2a38';
Chart.defaults.font.family  = "'Share Tech Mono', monospace";
Chart.defaults.font.size    = 10;

function streamingBase(yLabel, duration = 30_000) {
  return {
    type: 'line',
    data: { datasets: [] },
    options: {
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'nearest', intersect: false },
      plugins: {
        legend: {
          position: 'top',
          labels: { boxWidth: 10, padding: 12, color: '#6a8aaa' },
        },
        tooltip: { enabled: true },
        streaming: { duration, delay: 600, frameRate: 20 },
      },
      scales: {
        x: {
          type: 'realtime',
          realtime: { duration, delay: 600, frameRate: 20 },
          grid: { color: C.dimLine },
          ticks: { maxTicksLimit: 6 },
        },
        y: {
          position: 'left',
          grid: { color: C.dimLine },
          title: { display: true, text: yLabel, color: '#3a5a70' },
        },
      },
    },
  };
}

// ─── Voltage + Current chart ─────────────────────────────────────────────────
(function initVoltCurrChart() {
  const cfg = streamingBase('', 30_000);

  cfg.data.datasets = [
    {
      label: 'Voltage (V)',
      yAxisID: 'yVolt',
      borderColor: C.cyan,
      backgroundColor: C.cyan + '18',
      borderWidth: 1.5,
      pointRadius: 0,
      fill: true,
      tension: 0.3,
      data: [],
    },
    {
      label: 'Current (A)',
      yAxisID: 'yCurr',
      borderColor: C.amber,
      backgroundColor: C.amber + '18',
      borderWidth: 1.5,
      pointRadius: 0,
      fill: false,
      tension: 0.3,
      data: [],
    },
  ];

  cfg.options.scales = {
    x: cfg.options.scales.x,
    yVolt: {
      type: 'linear',
      position: 'left',
      grid: { color: C.dimLine },
      title: { display: true, text: 'Voltage (V)', color: C.cyan },
      ticks: { color: C.cyan },
      min: 290, max: 440,
    },
    yCurr: {
      type: 'linear',
      position: 'right',
      grid: { drawOnChartArea: false },
      title: { display: true, text: 'Current (A)', color: C.amber },
      ticks: { color: C.amber },
      min: -250, max: 400,
    },
  };

  const ctx = document.getElementById('chartVoltCurr');
  if (ctx) {
    CHARTS.voltCurr = new Chart(ctx, cfg);
  }
})();

// ─── Temperature chart ────────────────────────────────────────────────────────
(function initTempChart() {
  const cfg = streamingBase('°C', 30_000);

  cfg.data.datasets = [
    {
      label: 'Battery (°C)',
      borderColor: C.amber,
      backgroundColor: C.amber + '18',
      borderWidth: 1.5,
      pointRadius: 0,
      fill: true,
      tension: 0.3,
      data: [],
    },
    {
      label: 'Motor (°C)',
      borderColor: C.red,
      backgroundColor: C.red + '12',
      borderWidth: 1.5,
      pointRadius: 0,
      fill: false,
      tension: 0.3,
      data: [],
    },
    {
      label: 'Coolant (°C)',
      borderColor: C.cyan,
      backgroundColor: C.cyan + '12',
      borderWidth: 1.5,
      pointRadius: 0,
      fill: false,
      tension: 0.3,
      data: [],
    },
  ];

  cfg.options.scales.y.min = 10;
  cfg.options.scales.y.max = 130;

  const ctx = document.getElementById('chartTemp');
  if (ctx) {
    CHARTS.temp = new Chart(ctx, cfg);
  }
})();

// ─── Speed Gauge (canvas-drawn arc) ──────────────────────────────────────────
/**
 * Draws a circular arc gauge on the given canvas.
 * @param {HTMLCanvasElement} canvas
 * @param {number} value     Current value (0–max)
 * @param {number} max       Maximum value
 * @param {string} color     Arc colour
 */
function drawArcGauge(canvas, value, max, color = C.cyan) {
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  const cx = W / 2, cy = H / 2;
  const r  = Math.min(W, H) / 2 - 10;

  ctx.clearRect(0, 0, W, H);

  const startAngle = Math.PI * 0.75;            // 135° — bottom-left
  const endAngle   = Math.PI * 2.25;            // 405° — bottom-right (270° sweep)
  const fraction   = Math.min(value / max, 1.0);
  const fillEnd    = startAngle + fraction * (endAngle - startAngle);

  // Track
  ctx.beginPath();
  ctx.arc(cx, cy, r, startAngle, endAngle);
  ctx.strokeStyle = '#1c2a38';
  ctx.lineWidth   = 8;
  ctx.lineCap     = 'round';
  ctx.stroke();

  // Fill
  if (fraction > 0) {
    ctx.beginPath();
    ctx.arc(cx, cy, r, startAngle, fillEnd);
    ctx.strokeStyle = color;
    ctx.lineWidth   = 8;
    ctx.lineCap     = 'round';
    // Glow effect
    ctx.shadowColor = color;
    ctx.shadowBlur  = 12;
    ctx.stroke();
    ctx.shadowBlur  = 0;
  }

  // Tick marks every 20 km/h (for speed gauge)
  const tickCount = Math.floor(max / 20);
  for (let i = 0; i <= tickCount; i++) {
    const angle = startAngle + (i / tickCount) * (endAngle - startAngle);
    const inner = r - 12;
    const outer = r + 2;
    ctx.beginPath();
    ctx.moveTo(cx + inner * Math.cos(angle), cy + inner * Math.sin(angle));
    ctx.lineTo(cx + outer * Math.cos(angle), cy + outer * Math.sin(angle));
    ctx.strokeStyle = '#2e4a60';
    ctx.lineWidth   = 1;
    ctx.stroke();
  }
}

// ─── SOC Doughnut (thin ring style) ──────────────────────────────────────────
function drawSOCRing(canvas, soc) {
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  const cx = W / 2, cy = H / 2;
  const r  = Math.min(W, H) / 2 - 12;

  ctx.clearRect(0, 0, W, H);

  // Determine colour based on SOC level
  let color = C.green;
  if (soc <= 10) color = C.red;
  else if (soc <= 20) color = C.amber;

  // Background ring
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.strokeStyle = '#1c2a38';
  ctx.lineWidth   = 10;
  ctx.stroke();

  // SOC fill
  const startAngle = -Math.PI / 2;           // 12 o'clock
  const fillAngle  = startAngle + (soc / 100) * Math.PI * 2;

  ctx.beginPath();
  ctx.arc(cx, cy, r, startAngle, fillAngle);
  ctx.strokeStyle = color;
  ctx.lineWidth   = 10;
  ctx.lineCap     = 'round';
  ctx.shadowColor = color;
  ctx.shadowBlur  = 16;
  ctx.stroke();
  ctx.shadowBlur  = 0;
}

// ── Expose draw helpers globally ─────────────────────────────────────────────
window.drawArcGauge = drawArcGauge;
window.drawSOCRing  = drawSOCRing;

// ── Initial renders ───────────────────────────────────────────────────────────
const speedCanvas = document.getElementById('speedGauge');
const socCanvas   = document.getElementById('socRing');
if (speedCanvas) drawArcGauge(speedCanvas, 0, 220, C.cyan);
if (socCanvas)   drawSOCRing(socCanvas, 85);

// ─── Helper: push data point to streaming chart ───────────────────────────────
window.pushChartPoint = function(chart, datasetIndex, y) {
  if (!chart || !chart.data.datasets[datasetIndex]) return;
  chart.data.datasets[datasetIndex].data.push({ x: Date.now(), y });
  chart.update('quiet');
};
