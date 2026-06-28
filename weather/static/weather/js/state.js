'use strict';

import { MRU_KEY, MRU_MAX } from './constants.js';

// ── Global application state ────────────────────────────────
/**
 * @brief Global application state object.
 * @property {string}   lang              Current display language ('fi', 'sv', or 'en').
 * @property {Array}    stations          List of available weather stations.
 * @property {?number}  currentStationId  ID of the currently selected weather station.
 * @property {boolean}  showCamera        Whether to display weather camera images.
 * @property {boolean}  followLocation    Whether to always use geolocation to select nearest station.
 * @property {?number}  refreshTimer      Timeout ID for the scheduled weather refresh.
 * @property {?number}  countdownTimer    Interval ID for the countdown display timer.
 * @property {?number}  refreshDueAt      Epoch ms when new data will be available (null if unknown).
 * @property {boolean}  loading           Whether a weather data fetch is currently in progress.
 */
export const state = {
  lang: 'fi',
  stations: [],
  currentStationId: null,
  showCamera: true,
  followLocation: false,
  showHistory: true,
  historyHours: 12,
  refreshTimer: null,
  countdownTimer: null,
  refreshDueAt: null,
  loading: false,
};

// ── Forecast carousel state ─────────────────────────────────
export const forecastCarousel = { index: 0, items: [] };
export const FORECAST_PAGE_SIZE = 3;

// ── MRU (Most Recently Used) helpers ────────────────────────
export function loadMru() {
  try {
    const raw = localStorage.getItem(MRU_KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr.filter(n => Number.isInteger(n)) : [];
  } catch (_) {
    return [];
  }
}

export function saveMru(ids) {
  try {
    localStorage.setItem(MRU_KEY, JSON.stringify(ids));
  } catch (_) { /* ignore quota errors */ }
}

export function pushMru(stationId) {
  const id = parseInt(stationId, 10);
  if (!id) return;
  let mru = loadMru().filter(x => x !== id);
  mru.unshift(id);
  if (mru.length > MRU_MAX) mru = mru.slice(0, MRU_MAX);
  saveMru(mru);
}
