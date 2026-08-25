'use strict';

import { state } from './state.js';
import { dom } from './render.js';
import { fetchWeather, getCsrfToken, saveSettings } from './api.js';

/**
 * @brief Select the nearest weather station using the browser Geolocation API.
 *
 * Called on page load when no station has been saved yet, or on demand via
 * the locate button. Falls back to `stations[0]` (first alphabetically sorted
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
    saveSettings({ current_station_id: stations[0].id, current_station_name: stations[0].name });
    return fetchWeather(stations[0].id);
  };

  dom.stationLocateBtn.disabled = true;
  document.body.classList.add('loading');
  dom.weatherCard.classList.add('loading');

  try {
    if (!navigator.geolocation) {
      await fallback('Geolocation API not supported by this browser');
      return;
    }

    const position = await new Promise(resolve => {
      navigator.geolocation.getCurrentPosition(resolve, (err) => {
        console.warn(`[geolocation ${new Date().toISOString()}] Permission denied or unavailable:`, err.message);
        resolve(null);
      }, { timeout: 8000 });
    });

    if (!position) {
      await fallback('No position returned');
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
      saveSettings({ current_station_id: nearest.id, current_station_name: nearest.formatted_name || nearest.name });
      await fetchWeather(nearest.id);
    } catch (err) {
      await fallback(err.message);
    }
  } finally {
    dom.stationLocateBtn.disabled = false;
    document.body.classList.remove('loading');
    dom.weatherCard.classList.remove('loading');
  }
}
