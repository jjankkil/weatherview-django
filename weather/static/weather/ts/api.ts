"use strict";

import { state, pushMru } from "./state.js";
import {
  dom,
  labels,
  showError,
  hideError,
  renderWeather,
  populateStations,
} from "./render.js";
import { showCameraForStation, showStationDistance } from "./camera.js";
import { renderTrendChart, destroyTrendChart } from "./trend_chart.js";

type ApiLink = { href: string };
type ApiLinkMap = Record<string, ApiLink>;
let apiLinksPromise: Promise<ApiLinkMap> | null = null;

export async function getApiHref(relation: string) {
  if (!apiLinksPromise) {
    apiLinksPromise = fetch("/api/")
      .then((response) => {
        if (!response.ok)
          throw new Error(`API root returned HTTP ${response.status}`);
        return response.json();
      })
      .then((data) => data._links as ApiLinkMap)
      .catch((error) => {
        apiLinksPromise = null;
        throw error;
      });
  }
  const href = (await apiLinksPromise)[relation]?.href;
  if (!href) throw new Error(`API root does not advertise '${relation}'`);
  return href;
}

function getStationHref(stationId: number, relation: "self" | "history") {
  const station = state.stations.find((item) => item.id === stationId);
  const href = station?._links?.[relation]?.href;
  if (!href) throw new Error(`Station ${stationId} has no '${relation}' link`);
  return href;
}

// ── CSRF token ───────────────────────────────────────────────
export function getCsrfToken() {
  const meta = document.querySelector<HTMLMetaElement>(
    'meta[name="csrf-token"]',
  );
  return meta ? meta.content : "";
}

// ── Settings API ─────────────────────────────────────────────
/**
 * @brief Fetch and apply user settings from the backend session.
 * @return {Promise<void>} Always resolves (errors are ignored).
 */
export async function fetchSettings() {
  try {
    const r = await fetch(await getApiHref("settings"));
    if (!r.ok) return;
    const data = await r.json();
    if (data.language) state.lang = data.language;
    if (data.current_station_id)
      state.currentStationId = data.current_station_id;
    if (data.show_camera !== undefined) state.showCamera = data.show_camera;
    if (data.show_history !== undefined) state.showHistory = data.show_history;
    if (data.history_hours !== undefined)
      state.historyHours = data.history_hours;
  } catch (_) {
    /* ignore */
  }
}

export async function saveSettings(patch) {
  try {
    await fetch(await getApiHref("settings"), {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      body: JSON.stringify(patch),
    });
  } catch (_) {
    /* ignore */
  }
}

// ── Stations API ─────────────────────────────────────────────
export async function fetchStations() {
  dom.stationSelect.innerHTML = `<option value="">${labels().loadingStations}</option>`;
  try {
    const r = await fetch(await getApiHref("stations"));
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
    const r = await fetch(getStationHref(stationId, "history"));
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
  dom.nextUpdateLabel.textContent = "";
}

export function startNextUpdateDisplay(seconds) {
  clearCountdown();
  if (seconds <= 0) return;
  state.refreshDueAt = Date.now() + seconds * 1000;
  dom.nextUpdateLabel.textContent = labels().nextUpdate.replace("{s}", seconds);
  state.countdownTimer = setInterval(() => {
    const remaining = Math.ceil((state.refreshDueAt - Date.now()) / 1000);
    if (remaining <= 0) {
      clearInterval(state.countdownTimer);
      state.countdownTimer = null;
      dom.nextUpdateLabel.textContent = "";
    } else {
      dom.nextUpdateLabel.textContent = labels().nextUpdate.replace(
        "{s}",
        remaining,
      );
    }
  }, 1000);
  state.refreshTimer = setTimeout(() => {
    if (state.currentStationId) fetchWeather(state.currentStationId, true);
  }, seconds * 1000);
}

// ── Weather data API ─────────────────────────────────────────
let weatherRequestId = 0;

export async function fetchWeather(stationId, fresh = false) {
  const requestId = ++weatherRequestId;
  state.loading = true;
  clearCountdown();
  dom.refreshBtn.disabled = true;
  document.body.classList.add("loading");
  dom.weatherCard.classList.add("loading");
  hideError();

  try {
    const href = getStationHref(stationId, "self");
    const url = fresh ? `${href}?refresh=1` : href;
    const r = await fetch(url);

    if (!r.ok) {
      if (requestId !== weatherRequestId) return;
      let msg;
      try {
        const data = await r.json();
        msg = data.error;
      } catch (_) {
        /* response was not JSON */
      }
      if (!msg) msg = labels().serviceError.replace("{code}", r.status);
      showError(msg);
      return;
    }

    const data = await r.json();
    if (requestId !== weatherRequestId) return;
    renderWeather(data);
    pushMru(stationId);
    if (state.stations.length > 0) populateStations(state.stations);
    startNextUpdateDisplay(data.seconds_until_next_update || 0);
    showStationDistance(stationId);
    if (state.showCamera) showCameraForStation(stationId);
    if (state.showHistory) {
      fetchStationHistory(stationId).then(renderTrendChart);
    } else {
      destroyTrendChart();
    }
  } catch (e) {
    if (requestId === weatherRequestId) showError(labels().networkError);
  } finally {
    if (requestId !== weatherRequestId) return;
    state.loading = false;
    dom.refreshBtn.disabled = false;
    document.body.classList.remove("loading");
    dom.weatherCard.classList.remove("loading");
  }
}
