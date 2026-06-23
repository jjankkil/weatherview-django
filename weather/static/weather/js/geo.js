'use strict';

import { state } from './state.js';
import { dom } from './render.js';
import { fetchWeather, getCsrfToken } from './api.js';

/**
 * @brief Select the nearest weather station using the browser Geolocation API.
 *
 * Called on page load when `state.followLocation` is true or when no station
 * has been saved yet. Falls back to `stations[0]` (first alphabetically sorted
 * station) if geolocation is unavailable, denied, or times out.
 *
 * @note The Geolocation API is only available in secure contexts (HTTPS or
 *       localhost). On plain HTTP the fallback fires immediately.
 *
 * @param {Array} stations Full station list already fetched from `/api/stations/`.
 */
export async function selectNearestByGeolocation(stations) {
  if (!stations.length) return;

  const fallback = (reason) => {
    console.warn(`[geolocation ${new Date().toISOString()}] Falling back to first station:`, reason);
    state.currentStationId = stations[0].id;
    dom.stationSelect.value = String(stations[0].id);
    fetchWeather(stations[0].id);
  };

  if (!navigator.geolocation) {
    fallback('Geolocation API not supported by this browser');
    return;
  }

  const position = await new Promise(resolve => {
    navigator.geolocation.getCurrentPosition(resolve, (err) => {
      console.warn(`[geolocation ${new Date().toISOString()}] Permission denied or unavailable:`, err.message);
      resolve(null);
    }, { timeout: 8000 });
  });

  if (!position) {
    fallback('No position returned');
    return;
  }

  try {
    const { latitude, longitude } = position.coords;
    console.debug(`[geolocation] Got position: lat=${latitude}, lon=${longitude}`);
    const r = await fetch('/api/nearest-station/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ lat: latitude, lon: longitude }),
    });
    if (!r.ok) throw new Error(`nearest-station responded with HTTP ${r.status}`);
    const nearest = await r.json();
    console.debug('[geolocation] Nearest station:', nearest.formatted_name);
    state.currentStationId = nearest.id;
    dom.stationSelect.value = String(nearest.id);
    fetchWeather(nearest.id);
  } catch (err) {
    fallback(err.message);
  }
}
