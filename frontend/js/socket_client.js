/**
 * socket_client.js
 * Manages the Socket.IO connection to the Flask backend.
 *
 * Responsibilities:
 *  - Connect / reconnect automatically
 *  - Receive "telemetry" events and distribute to the UI layer
 *  - Emit control commands (drive mode, trip reset)
 *  - Update connection status badge
 */

'use strict';

// ── Connection ────────────────────────────────────────────────────────────────
// When running from Flask's static serve the backend is on the same origin.
// For standalone HTML dev (e.g. Live Server), point to http://localhost:5000
const BACKEND_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? `${window.location.protocol}//${window.location.hostname}:5000`
  : window.location.origin;

const socket = io(BACKEND_URL, {
  reconnectionAttempts: Infinity,
  reconnectionDelay: 1500,
  timeout: 8000,
  transports: ['websocket', 'polling'],
});

// ── Status DOM refs ───────────────────────────────────────────────────────────
const wsStatusEl = document.getElementById('wsStatus');

function setStatus(state) {
  if (!wsStatusEl) return;
  const labels = {
    connecting: { text: '⬤ CONNECTING', cls: '' },
    connected:  { text: '⬤ CONNECTED',  cls: 'connected' },
    error:      { text: '⬤ OFFLINE',    cls: 'error' },
  };
  const s = labels[state] || labels.connecting;
  wsStatusEl.textContent = s.text;
  wsStatusEl.className   = `ws-status ${s.cls}`;
}

// ── Lifecycle events ──────────────────────────────────────────────────────────
socket.on('connect', () => {
  setStatus('connected');
  console.info('[WS] Connected — SID:', socket.id);
  // Ask for an immediate snapshot instead of waiting for the next tick
  socket.emit('request_snapshot');
});

socket.on('disconnect', () => {
  setStatus('error');
  console.warn('[WS] Disconnected');
});

socket.on('connect_error', (err) => {
  setStatus('error');
  console.error('[WS] Connection error:', err.message);
});

// ── Config received on connect ────────────────────────────────────────────────
socket.on('config', (cfg) => {
  console.info('[WS] Received vehicle config:', cfg);
  window.VEHICLE_CONFIG = cfg;  // make available globally
});

// ── Telemetry stream ──────────────────────────────────────────────────────────
socket.on('telemetry', (data) => {
  // Validate minimum shape before touching the DOM
  if (!data || !data.battery || !data.motor || !data.vehicle) return;

  // Dispatch to UI updater (defined in ui.js)
  if (typeof window.updateDashboard === 'function') {
    window.updateDashboard(data);
  }
});

// ── Server acknowledgements ───────────────────────────────────────────────────
socket.on('drive_mode_changed', ({ mode }) => {
  console.info('[WS] Drive mode changed to:', mode);
  if (typeof window.onDriveModeChanged === 'function') {
    window.onDriveModeChanged(mode);
  }
});

socket.on('trip_reset', () => {
  console.info('[WS] Trip reset confirmed');
});

// ── Public control API ────────────────────────────────────────────────────────
window.socketSend = {
  setDriveMode(mode) {
    socket.emit('set_drive_mode', { mode });
  },
  resetTrip() {
    socket.emit('reset_trip');
  },
};
