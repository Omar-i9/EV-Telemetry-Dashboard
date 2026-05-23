/**
 * app.js — Main frontend entry point
 *
 * Responsibilities:
 *  - Wire all interactive controls (drive mode buttons, trip reset)
 *  - Handle page visibility changes (pause/resume when tab hidden)
 *  - HTTP fallback polling if WebSocket is unavailable
 *  - Keyboard shortcuts for drive mode switching
 */

'use strict';

// ── Drive Mode Buttons ────────────────────────────────────────────────────────
document.querySelectorAll('.dm-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const mode = btn.dataset.mode;
    if (!mode) return;

    // Optimistic UI update — don't wait for server ACK
    document.querySelectorAll('.dm-btn').forEach(b => b.classList.remove('dm-btn--active'));
    btn.classList.add('dm-btn--active');

    // Send to backend via WebSocket
    if (window.socketSend) {
      window.socketSend.setDriveMode(mode);
    }

    // Also available via REST for non-WS environments
    fetch('/api/control/drive-mode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode }),
    }).catch(() => {}); // silent fallback
  });
});

// ── Trip Reset Button ─────────────────────────────────────────────────────────
const btnReset = document.getElementById('btnResetTrip');
if (btnReset) {
  btnReset.addEventListener('click', () => {
    if (!confirm('Reset current trip statistics?')) return;
    if (window.socketSend) {
      window.socketSend.resetTrip();
    }
    // Optimistically clear the trip stats display
    ['tripDist','tripTime','tripAvgSpeed','tripConsumption'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.textContent = id === 'tripTime' ? '00:00' : '0';
    });
  });
}

// ── Keyboard Shortcuts ────────────────────────────────────────────────────────
// 1 = ECO, 2 = NORMAL, 3 = SPORT, 4 = LUDICROUS
const modeKeys = { '1': 'ECO', '2': 'NORMAL', '3': 'SPORT', '4': 'LUDICROUS' };
document.addEventListener('keydown', e => {
  // Don't intercept when typing in an input
  if (e.target.tagName === 'INPUT') return;
  const mode = modeKeys[e.key];
  if (mode) {
    const btn = document.querySelector(`.dm-btn[data-mode="${mode}"]`);
    if (btn) btn.click();
  }
});

// ── Page Visibility — pause WS if tab is hidden ───────────────────────────────
// (Socket.IO handles reconnection automatically; this is just a log hook)
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    console.info('[App] Tab hidden — telemetry paused in UI');
  } else {
    console.info('[App] Tab visible — telemetry resuming');
    // Request a fresh snapshot immediately on return
    if (window.socketSend && typeof window.socketSend.requestSnapshot === 'function') {
      window.socketSend.requestSnapshot();
    }
  }
});

// ── HTTP Fallback Polling ─────────────────────────────────────────────────────
// If the WebSocket never connects (e.g., running HTML file directly),
// fall back to polling /api/telemetry every second.
let _wsEverConnected = false;
let _pollInterval    = null;

// Wait 4 s; if WebSocket hasn't connected yet, start polling
setTimeout(() => {
  const statusEl = document.getElementById('wsStatus');
  if (statusEl && !statusEl.classList.contains('connected')) {
    console.warn('[App] WebSocket unavailable — falling back to HTTP polling');
    _pollInterval = setInterval(async () => {
      try {
        const res  = await fetch('/api/telemetry');
        if (!res.ok) return;
        const data = await res.json();
        if (typeof window.updateDashboard === 'function') {
          window.updateDashboard(data);
        }
      } catch (err) {
        console.error('[App] Poll error:', err);
      }
    }, 1000);
  }
}, 4000);

// Stop polling once WS connects
const _wsStatusObserver = new MutationObserver(() => {
  const statusEl = document.getElementById('wsStatus');
  if (statusEl && statusEl.classList.contains('connected') && _pollInterval) {
    clearInterval(_pollInterval);
    _pollInterval = null;
    console.info('[App] WS connected — stopped HTTP polling');
  }
});
const statusEl = document.getElementById('wsStatus');
if (statusEl) {
  _wsStatusObserver.observe(statusEl, { attributes: true, attributeFilter: ['class'] });
}

// ── Console welcome message ───────────────────────────────────────────────────
console.log('%c⚡ EV TELEMETRY DASHBOARD v1.0', 'color:#00d4ff;font-size:14px;font-weight:bold;');
console.log('%cBackend: ' + (window.location.origin), 'color:#6a8aaa');
console.log('%cKeyboard shortcuts: [1] ECO  [2] NORMAL  [3] SPORT  [4] LUDICROUS', 'color:#6a8aaa');
