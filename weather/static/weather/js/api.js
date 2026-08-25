'use strict';

import { state, pushMru } from './state.js';
import {
  dom, labels, showError, hideError, renderWeather, populateStations,
} from './render.js';
import { showCameraForStation } from './camera.js';
import { renderTrendChart, destroyTrendChart } from './trend_chart.js';

// ── CSRF token ───────────────────────────────────────────────
export function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.content : '';
}

// ── Settings API ─────────────────────────────────────────────
/**
 * @brief Fetch and apply user settings from the backend session.
 * @return {Promise<void>} Always resolves (errors are ignored).
 */
export async function fetchSettings() {
  try {
    const r = await fetch('/api/settings/');
    if (!r.ok) return;
    const data = await r.json();
    if (data.language) state.lang = data.language;
    if (data.current_station_id) state.currentStationId = data.current_station_id;
    if (data.show_camera !== undefined) state.showCamera = data.show_camera;
    if (data.show_history !== undefined) state.showHistory = data.show_history;
    if (data.history_hours !== undefined) state.historyHours = data.history_hours;
  } catch (_) { /* ignore */ }
}

export async function saveSettings(patch) {
  try {
    await fetch('/api/settings/save/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify(patch),
    });
  } catch (_) { /* ignore */ }
}

// ── Stations API ─────────────────────────────────────────────
export async function fetchStations() {
  dom.stationSelect.innerHTML = `<option value="">${labels().loadingStations}</option>`;
  try {
    const r = await fetch('/api/stations/');
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      showError(d.error || `HTTP ${r.status}`);
      return [];
    }
    const data = await r.json();
    return data.stations || [];
  } catch (e) {
    showError(String(e));
    return [];
  }
}

// ── Station history API ──────────────────────────────────────
/**
 * @brief Fetch hourly-bucketed temperature and precipitation history for a station.
 * @param {number} stationId  Digitraffic station ID.
 * @return {Promise<Object|null>}  History payload, or null on error.
 */
export async function fetchStationHistory(stationId) {
  try {
    const r = await fetch(`/api/station-history/${stationId}/`);
    if (!r.ok) return null;
    return await r.json();
  } catch (_) {
    return null;
  }
}

// ── Countdown timer ──────────────────────────────────────────
export function clearCountdown() {
  clearInterval(state.countdownTimer);
  clearTimeout(state.refreshTimer);
  state.countdownTimer = null;
  state.refreshTimer = null;
  state.refreshDueAt = null;
  dom.nextUpdateLabel.textContent = '';
}

export function startNextUpdateDisplay(seconds) {
  clearCountdown();
  if (seconds <= 0) return;
  state.refreshDueAt = Date.now() + seconds * 1000;
  dom.nextUpdateLabel.textContent = labels().nextUpdate.replace('{s}', seconds);
  state.countdownTimer = setInterval(() => {
    const remaining = Math.ceil((state.refreshDueAt - Date.now()) / 1000);
    if (remaining <= 0) {
      clearInterval(state.countdownTimer);
      state.countdownTimer = null;
      dom.nextUpdateLabel.textContent = '';
    } else {
      dom.nextUpdateLabel.textContent = labels().nextUpdate.replace('{s}', remaining);
    }
  }, 1000);
  state.refreshTimer = setTimeout(() => {
    if (state.currentStationId) fetchWeather(state.currentStationId, true);
  }, seconds * 1000);
}

// ── Weather data API ─────────────────────────────────────────
export async function fetchWeather(stationId, fresh = false) {
  if (state.loading) return;
  state.loading = true;
  clearCountdown();
  dom.refreshBtn.disabled = true;
  document.body.classList.add('loading');
  dom.weatherCard.classList.add('loading');
  hideError();

  try {
    const url = fresh ? `/api/station/${stationId}/?refresh=1` : `/api/station/${stationId}/`;
    const r = await fetch(url);

    if (!r.ok) {
      let msg;
      try {
        const data = await r.json();
        msg = data.error;
      } catch (_) { /* response was not JSON */ }
      if (!msg) msg = labels().serviceError.replace('{code}', r.status);
      showError(msg);
      return;
    }

    const data = await r.json();
    renderWeather(data);
    pushMru(stationId);
    if (state.stations.length > 0) populateStations(state.stations);
    startNextUpdateDisplay(data.seconds_until_next_update || 0);
    if (state.showCamera) showCameraForStation(stationId);
    if (state.showHistory) {
      fetchStationHistory(stationId).then(renderTrendChart);
    } else {
      destroyTrendChart();
    }
  } catch (e) {
    showError(labels().networkError);
  } finally {
    state.loading = false;
    dom.refreshBtn.disabled = false;
    document.body.classList.remove('loading');
    dom.weatherCard.classList.remove('loading');
  }
}
