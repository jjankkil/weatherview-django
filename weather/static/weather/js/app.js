'use strict';

// ── i18n ────────────────────────────────────────────────────
const LABELS = {
  fi: {
    appTitle: 'Tiesää',
    stationLabel: 'Asema:',
    obsTime: 'Havaintoaika:',
    temperature: 'Lämpötila:',
    feelsLike: 'Tuntuu kuin:',
    tempChange: 'Lämpötilan muutos:',
    wind: 'Tuulen nopeus (ka.):',
    windDir: 'Tuulen suunta:',
    windMax: 'Maksimituuli:',
    humidity: 'Ilman kosteus:',
    visibility: 'Näkyvyys:',
    forecastTitle: 'Ennuste',
    refresh: 'Päivitä nyt',
    loading: 'Ladataan…',
    loadingStations: '— Ladataan asemia… —',
    nextUpdate: 'Seuraava päivitys: {s} s',
    settingsTitle: 'Asetukset',
    apiKeyLabel: 'OpenWeatherMap API-avain:',
    apiKeyHint: 'API-avain tarvitaan säätilan symbolien ja ennusteen näyttämiseen. Rekisteröidy ilmaiseksi osoitteessa openweathermap.org.',
    cameraLabel: 'Näytä kelikameroiden kuvat:',
    save: 'Tallenna',
    cancel: 'Peruuta',
    langToggle: 'EN',
  },
  en: {
    appTitle: 'Road Weather',
    stationLabel: 'Station:',
    obsTime: 'Observation time:',
    temperature: 'Temperature:',
    feelsLike: 'Feels like:',
    tempChange: 'Temperature change:',
    wind: 'Wind speed (avg):',
    windDir: 'Wind direction:',
    windMax: 'Max wind:',
    humidity: 'Humidity:',
    visibility: 'Visibility:',
    forecastTitle: 'Forecast',
    refresh: 'Refresh now',
    loading: 'Loading…',
    loadingStations: '— Loading stations… —',
    nextUpdate: 'Next update: {s} s',
    settingsTitle: 'Settings',
    apiKeyLabel: 'OpenWeatherMap API key:',
    apiKeyHint: 'API key required for weather symbols and forecast. Register for free at openweathermap.org.',
    cameraLabel: 'Show weather camera images:',
    save: 'Save',
    cancel: 'Cancel',
    langToggle: 'FI',
  },
};

// ── State ───────────────────────────────────────────────────
/**
 * @brief Global application state object.
 * @property {string} lang Current display language ('fi' or 'en').
 * @property {Array} stations List of available weather stations.
 * @property {?number} currentStationId ID of the currently selected weather station.
 * @property {string} apiKey OpenWeatherMap API key for weather symbols and forecast.
 * @property {boolean} showCamera Whether to display weather camera images.
 * @property {?number} refreshTimer Timeout ID for the scheduled weather refresh.
 * @property {?number} countdownTimer Interval ID for the countdown display timer.
 * @property {number} countdownValue Seconds remaining until next automatic refresh.
 * @property {boolean} loading Whether a weather data fetch is currently in progress.
 */
const state = {
  lang: 'fi',
  stations: [],
  currentStationId: null,
  apiKey: '',
  showCamera: true,
  refreshTimer: null,
  countdownTimer: null,
  countdownValue: 0,
  loading: false,
};

// ── Camera ──────────────────────────────────────────────────

/** @brief In-memory cache of GeoJSON features from the camera stations API. null until first fetch. */
let cameraStations = null;

/**
 * @brief Calculate the great-circle distance between two WGS84 coordinates.
 *
 * Uses the haversine formula.
 *
 * @param {number} lat1 Latitude of the first point in decimal degrees.
 * @param {number} lon1 Longitude of the first point in decimal degrees.
 * @param {number} lat2 Latitude of the second point in decimal degrees.
 * @param {number} lon2 Longitude of the second point in decimal degrees.
 * @return {number} Distance in kilometres.
 */
function haversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

/**
 * @brief Fetch and cache the full Digitraffic weathercam station list.
 *
 * Retrieves GeoJSON features from CAMERA_STATIONS_URL on first call and
 * stores the result in the module-level cameraStations cache for subsequent calls.
 *
 * @return {Promise<?Array>} Resolves to the array of GeoJSON feature objects,
 *         or null if the request fails.
 */
async function loadCameraStations() {
  if (cameraStations) return cameraStations;
  try {
    const r = await fetch(CAMERA_STATIONS_URL);
    if (!r.ok) return null;
    const data = await r.json();
    cameraStations = data.features || [];
    return cameraStations;
  } catch (_) {
    return null;
  }
}

/**
 * @brief Calculate the initial bearing from one WGS84 point to another.
 *
 * @param {number} lat1 Latitude of the origin in decimal degrees.
 * @param {number} lon1 Longitude of the origin in decimal degrees.
 * @param {number} lat2 Latitude of the destination in decimal degrees.
 * @param {number} lon2 Longitude of the destination in decimal degrees.
 * @return {number} Bearing in degrees [0, 360), clockwise from north.
 */
function bearingDeg(lat1, lon1, lat2, lon2) {
  const toRad = x => x * Math.PI / 180;
  const dLon = toRad(lon2 - lon1);
  const y = Math.sin(dLon) * Math.cos(toRad(lat2));
  const x = Math.cos(toRad(lat1)) * Math.sin(toRad(lat2)) -
            Math.sin(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.cos(dLon);
  return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
}

/**
 * @brief Convert a bearing in degrees to a localised direction label.
 *
 * Snaps the bearing to the nearest of 8 compass points (45° sectors).
 *
 * @param {number} deg Bearing in degrees [0, 360).
 * @param {string} lang Language code ('fi' or 'en').
 * @return {string} Localised direction string, e.g. "etelään" or "south".
 */
function bearingLabel(deg, lang) {
  const dirs = lang === 'en' ? DIRECTIONS_EN : DIRECTIONS_FI;
  return dirs[Math.round(deg / 45) % 8];
}

/**
 * @brief Find the weathercam station closest to a given coordinate.
 *
 * Iterates all GeoJSON features and returns the one with the minimum
 * haversine distance to the given point.
 *
 * @param {Array} stations Array of GeoJSON feature objects from the camera stations API.
 * @param {number} lat Reference latitude in decimal degrees.
 * @param {number} lon Reference longitude in decimal degrees.
 * @return {?{feature: Object, distanceKm: number}} The nearest feature and its distance,
 *         or null if the stations array is empty.
 */
function findNearestCamera(stations, lat, lon) {
  let best = null, bestDist = Infinity;
  for (const f of stations) {
    const [fLon, fLat] = f.geometry.coordinates;
    const d = haversineKm(lat, lon, fLat, fLon);
    if (d < bestDist) { bestDist = d; best = f; }
  }
  return best ? { feature: best, distanceKm: bestDist } : null;
}

// ── Carousel state ───────────────────────────────────────────

/**
 * @brief Mutable state for the camera image carousel.
 * @property {number} index  Index of the currently visible slide.
 * @property {Array}  slides Array of preset objects augmented with a `loaded` boolean.
 */
const carousel = { index: 0, slides: [] };

/**
 * @brief Navigate the carousel to a specific slide index.
 *
 * Translates the track element, updates the prev/next button disabled states,
 * and refreshes the camera footer text with the load time and pointing direction
 * of the newly visible slide.
 *
 * @param {number} i Zero-based index of the target slide.
 */
function carouselGoTo(i) {
  carousel.index = i;
  dom.carouselTrack.style.transform = `translateX(-${i * 100}%)`;
  dom.carouselPrev.disabled = i === 0;
  dom.carouselNext.disabled = i === carousel.slides.length - 1;
  const slide = carousel.slides[i];
  if (slide) {
    const now = new Date();
    const timeStr = now.toLocaleTimeString(state.lang === 'en' ? 'en-GB' : 'fi-FI');
    const loadedStr = state.lang === 'en' ? `Loaded ${timeStr}` : `Ladattu ${timeStr}`;
    dom.cameraUpdated.textContent = slide.loaded
      ? (slide.presentationName ? `${loadedStr} · ${state.lang === 'en' ? 'Direction' : 'Suunta'} ${slide.presentationName}` : loadedStr)
      : (slide.presentationName ? `${state.lang === 'en' ? 'Direction' : 'Suunta'} ${slide.presentationName}` : '');
  }
}

/**
 * @brief Populate the carousel DOM with one slide per camera preset.
 *
 * Clears the existing carousel track and creates a slide for each preset.
 * Each slide shows a loading spinner while its image is fetching, then replaces
 * the spinner with the loaded image. A direction label overlay is added when
 * the preset has a presentationName. Images are cache-busted with the timestamp ts.
 *
 * @param {Array}  presets Array of preset objects (id, presentationName, inCollection, …).
 * @param {number} ts      Timestamp appended as a cache-bust query parameter.
 */
function buildCarousel(presets, ts) {
  carousel.slides = presets.map(p => ({ ...p, loaded: false }));
  carousel.index = 0;
  dom.carouselTrack.innerHTML = '';

  for (const preset of presets) {
    const slide = document.createElement('div');
    slide.className = 'carousel-slide';

    const loading = document.createElement('div');
    loading.className = 'carousel-slide-loading';
    loading.textContent = '⏳';
    slide.appendChild(loading);

    if (preset.presentationName) {
      const label = document.createElement('div');
      label.className = 'carousel-slide-label';
      label.textContent = preset.presentationName;
      slide.appendChild(label);
    }

    const imgUrl = `${CAMERA_IMAGE_BASE}${preset.id}.jpg?t=${ts}`;
    const img = new Image();
    img.onload = () => {
      img.className = '';
      loading.replaceWith(img);
      const idx = carousel.slides.findIndex(s => s.id === preset.id);
      if (idx >= 0) carousel.slides[idx].loaded = true;
      if (carousel.index === idx) carouselGoTo(idx);
    };
    img.onerror = () => {
      const err = document.createElement('div');
      err.className = 'carousel-slide-error';
      err.textContent = state.lang === 'en' ? 'Image unavailable' : 'Kuva ei saatavilla';
      loading.replaceWith(err);
    };
    img.src = imgUrl;
    dom.carouselTrack.appendChild(slide);
  }

  dom.carouselPrev.disabled = true;
  dom.carouselNext.disabled = presets.length <= 1;
  dom.carouselTrack.style.transform = 'translateX(0)';

  const first = presets[0];
  dom.cameraUpdated.textContent = first?.presentationName
    ? `${state.lang === 'en' ? 'Direction' : 'Suunta'} ${first.presentationName}`
    : '';
}

/**
 * @brief Find the nearest weathercam to a weather station and display it in the carousel.
 *
 * Loads the camera station list (cached after first call), finds the closest camera
 * to the selected weather station by haversine distance, fetches the camera's detail
 * endpoint to obtain presentationName for each preset, then calls buildCarousel to
 * render all active presets as carousel slides.
 *
 * @param {number} stationId FMI station ID of the currently selected weather station.
 * @details
 * - Silently returns if the weather station has no coordinates.
 * - Falls back to preset IDs without presentationName if the detail request fails.
 * - Camera panel is made visible before image fetching begins.
 */
async function showCameraForStation(stationId) {
  const station = state.stations.find(s => s.id === stationId);
  if (!station || station.lat == null || station.lon == null) return;

  const camStations = await loadCameraStations();
  if (!camStations || camStations.length === 0) return;

  const result = findNearestCamera(camStations, station.lat, station.lon);
  if (!result) return;

  const { feature, distanceKm } = result;

  const [camLon, camLat] = feature.geometry.coordinates;
  const bearing = bearingDeg(station.lat, station.lon, camLat, camLon);
  const dirLabel = bearingLabel(bearing, state.lang);
  const distM = Math.round(distanceKm * 1000);
  const distLabel = distanceKm < 1
    ? `${distM} m ${dirLabel}`
    : `${distanceKm.toFixed(1)} km ${dirLabel}`;

  const rawName = feature.properties.name || feature.properties.id || '';
  dom.cameraTitle.textContent = rawName.replace(/_/g, ' ');
  dom.cameraDistance.textContent = distLabel;
  dom.cameraUpdated.textContent = '';
  setVisible(dom.cameraPanel, true);

  // Fetch detail for presentationName on all presets
  let presets = (feature.properties.presets || []).filter(p => p.inCollection);
  try {
    const dr = await fetch(`${CAMERA_STATIONS_URL}/${feature.properties.id}`);
    if (dr.ok) {
      const detail = await dr.json();
      const detailMap = new Map((detail.properties?.presets || []).map(p => [p.id, p]));
      presets = presets.map(p => ({ ...p, ...(detailMap.get(p.id) || {}) }));
    }
  } catch (_) { /* use presets without presentationName */ }

  if (presets.length === 0) return;
  buildCarousel(presets, Date.now());
}

// ── DOM refs ────────────────────────────────────────────────
const $ = id => document.getElementById(id);

const dom = {
  appTitle:       $('app-title'),
  stationLabel:   $('station-label'),
  stationSelect:  $('station-select'),
  errorBanner:    $('error-banner'),
  weatherCard:    $('weather-card'),
  obsTimeLabel:   $('obs-time-label'),
  obsTimeValue:   $('obs-time-value'),
  symbolRow:      $('symbol-row'),
  currentSymbol:  $('current-symbol'),
  tempLabel:      $('temp-label'),
  tempValue:      $('temp-value'),
  feelsLabel:     $('feels-label'),
  feelsValue:     $('feels-value'),
  feelsRow:       $('feels-row'),
  tempChangeLabel:$('temp-change-label'),
  tempChangeValue:$('temp-change-value'),
  tempChangeRow:  $('temp-change-row'),
  windLabel:      $('wind-label'),
  windValue:      $('wind-value'),
  windDirLabel:   $('wind-dir-label'),
  windDirValue:   $('wind-dir-value'),
  windDirRow:     $('wind-dir-row'),
  windMaxLabel:   $('wind-max-label'),
  windMaxValue:   $('wind-max-value'),
  humidityLabel:  $('humidity-label'),
  humidityValue:  $('humidity-value'),
  humidityRow:    $('humidity-row'),
  visibilityLabel:$('visibility-label'),
  visibilityValue:$('visibility-value'),
  visibilityRow:  $('visibility-row'),
  pwLabel:        $('pw-label'),
  pwValue:        $('pw-value'),
  pwRow:          $('pw-row'),
  forecastSection:$('forecast-section'),
  forecastTitle:  $('forecast-title'),
  forecastItems:  $('forecast-items'),
  refreshBtn:     $('refresh-btn'),
  refreshLabel:   $('refresh-label'),
  nextUpdateLabel:$('next-update-label'),
  langToggle:     $('lang-toggle'),
  settingsBtn:    $('settings-btn'),
  settingsModal:  $('settings-modal'),
  settingsTitle:  $('settings-modal-title'),
  apiKeyInput:    $('api-key-input'),
  apiKeyLabel:    null,  // set after DOMContentLoaded
  cameraToggle:   $('camera-toggle'),
  cameraLabel:    null,  // set after DOMContentLoaded
  settingsSave:   $('settings-save'),
  settingsCancel: $('settings-cancel'),
  settingsClose:  $('settings-close'),
  cameraPanel:    $('camera-panel'),
  cameraTitle:    $('camera-title'),
  cameraDistance: $('camera-distance'),
  cameraUpdated:  $('camera-updated'),
  carouselTrack:  $('carousel-track'),
  carouselPrev:   $('carousel-prev'),
  carouselNext:   $('carousel-next'),
};

// ── Helpers ──────────────────────────────────────────────────
function showError(msg) {
  dom.errorBanner.textContent = msg;
  dom.errorBanner.classList.remove('hidden');
}

function hideError() {
  dom.errorBanner.classList.add('hidden');
}

function setVisible(el, visible) {
  if (visible) el.classList.remove('hidden');
  else el.classList.add('hidden');
}

function setText(el, value) {
  el.textContent = value || '';
}

function clearCountdown() {
  clearInterval(state.countdownTimer);
  clearTimeout(state.refreshTimer);
  state.countdownTimer = null;
  state.refreshTimer = null;
  dom.nextUpdateLabel.textContent = '';
}

function scheduleRefresh(seconds) {
  clearCountdown();
  if (seconds <= 0) return;

  state.countdownValue = seconds;
  dom.nextUpdateLabel.textContent = labels().nextUpdate.replace('{s}', seconds);

  state.countdownTimer = setInterval(() => {
    state.countdownValue -= 1;
    if (state.countdownValue <= 0) {
      clearCountdown();
    } else {
      dom.nextUpdateLabel.textContent = labels().nextUpdate.replace('{s}', state.countdownValue);
    }
  }, 1000);

  state.refreshTimer = setTimeout(() => {
    if (state.currentStationId) fetchWeather(state.currentStationId);
  }, seconds * 1000);
}

function labels() {
  return LABELS[state.lang];
}

function applyLabels() {
  const L = labels();
  setText(dom.appTitle, L.appTitle);
  setText(dom.stationLabel, L.stationLabel);
  setText(dom.obsTimeLabel, L.obsTime);
  setText(dom.tempLabel, L.temperature);
  setText(dom.feelsLabel, L.feelsLike);
  setText(dom.tempChangeLabel, L.tempChange);
  setText(dom.windLabel, L.wind);
  setText(dom.windDirLabel, L.windDir);
  setText(dom.windMaxLabel, L.windMax);
  setText(dom.humidityLabel, L.humidity);
  setText(dom.visibilityLabel, L.visibility);
  setText(dom.forecastTitle, L.forecastTitle);
  setText(dom.refreshLabel, L.refresh);
  dom.langToggle.title = `Switch to ${L.langToggle}`;
  dom.langToggle.textContent = L.langToggle;
  if (dom.apiKeyLabel) setText(dom.apiKeyLabel, L.apiKeyLabel);
  if (dom.cameraLabel) setText(dom.cameraLabel, L.cameraLabel);
  const hint = document.querySelector('.settings-hint');
  if (hint) hint.textContent = L.apiKeyHint;
  const settingsSave = dom.settingsSave;
  if (settingsSave) setText(settingsSave, L.save);
  const settingsCancel = dom.settingsCancel;
  if (settingsCancel) setText(settingsCancel, L.cancel);
  setText(dom.settingsTitle, L.settingsTitle);
  document.documentElement.lang = state.lang;
}

// ── API calls ────────────────────────────────────────────────
/**
 * @brief Fetch and apply user settings from the backend session.
 *
 * Retrieves user preferences (language, API key, current station, camera visibility)
 * from the server and updates the global state. Gracefully handles network errors
 * by silently ignoring failures and retaining current state values.
 *
 * @return {Promise<void>} Always resolves (errors are ignored).
 * @details
 * - Updates state.lang with user's language preference
 * - Updates state.apiKey with OpenWeatherMap API key (empty string if not set)
 * - Updates state.currentStationId with last selected station (null if not set)
 * - Updates state.showCamera with camera visibility preference (defaults to true)
 * - Network errors are silently caught; state retains default values on failure
 */
async function fetchSettings() {
  try {
    const r = await fetch('/api/settings/');
    if (!r.ok) return;
    const data = await r.json();
    if (data.language) state.lang = data.language;
    if (data.openweathermap_api_key) state.apiKey = data.openweathermap_api_key;
    if (data.current_station_id) state.currentStationId = data.current_station_id;
    if (data.show_camera !== undefined) state.showCamera = data.show_camera;
  } catch (_) { /* ignore */ }
}

async function saveSettings(patch) {
  try {
    await fetch('/api/settings/save/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    });
  } catch (_) { /* ignore */ }
}

async function fetchStations() {
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

async function fetchWeather(stationId) {
  if (state.loading) return;
  state.loading = true;
  clearCountdown();
  dom.refreshBtn.disabled = true;
  document.body.classList.add('loading');
  dom.weatherCard.classList.add('loading');
  hideError();

  try {
    const r = await fetch(`/api/station/${stationId}/`);
    const data = await r.json();

    if (!r.ok || data.error) {
      showError(data.error || `HTTP ${r.status}`);
      scheduleRefresh(60);
      return;
    }

    renderWeather(data);
    pushMru(stationId);
    if (state.stations.length > 0) populateStations(state.stations);
    scheduleRefresh(data.seconds_until_next_update || 60);
    // Only load and display camera if user has enabled it in settings
    if (state.showCamera) showCameraForStation(stationId);
  } catch (e) {
    showError(String(e));
    scheduleRefresh(60);
  } finally {
    state.loading = false;
    dom.refreshBtn.disabled = false;
    document.body.classList.remove('loading');
    dom.weatherCard.classList.remove('loading');
  }
}

// ── Render ───────────────────────────────────────────────────
function renderWeather(data) {
  setText(dom.obsTimeValue, data.observation_time || '—');

  setText(dom.tempValue, data.temperature || '—');

  setVisible(dom.feelsRow, !!data.feels_like);
  setText(dom.feelsValue, data.feels_like);

  setVisible(dom.tempChangeRow, !!data.temperature_change);
  setText(dom.tempChangeValue, data.temperature_change);

  setText(dom.windValue, data.wind_speed || '—');

  setVisible(dom.windDirRow, !!data.wind_direction);
  setText(dom.windDirValue, data.wind_direction);

  setText(dom.windMaxValue, data.wind_max || '—');

  setVisible(dom.humidityRow, !!data.humidity);
  setText(dom.humidityValue, data.humidity);

  setVisible(dom.visibilityRow, !!data.visibility);
  setText(dom.visibilityValue, data.visibility);

  // Present weather - label comes from backend
  const hasPW = !!data.present_weather;
  setVisible(dom.pwRow, hasPW);
  if (hasPW) {
    setText(dom.pwLabel, data.present_weather_label || labels().fi?.weather || 'Säätila:');
    setText(dom.pwValue, data.present_weather);
  }

  // Current weather symbol
  const hasSymbol = !!data.current_symbol;
  setVisible(dom.symbolRow, hasSymbol);
  setText(dom.currentSymbol, data.current_symbol);

  // Forecast
  const forecasts = data.forecast || [];
  setVisible(dom.forecastSection, forecasts.length > 0);
  dom.forecastItems.innerHTML = '';
  for (const f of forecasts) {
    const item = document.createElement('div');
    item.className = 'forecast-item';
    item.innerHTML = `
      <span class="forecast-time">${esc(f.time)}</span>
      <span class="forecast-symbol">${esc(f.symbol) || '—'}</span>
      <span class="forecast-temp">${esc(f.temperature)}</span>
    `;
    dom.forecastItems.appendChild(item);
  }

  setVisible(dom.weatherCard, true);
}

function esc(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}


function loadMru() {
  try {
    const raw = localStorage.getItem(MRU_KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr.filter(n => Number.isInteger(n)) : [];
  } catch (_) {
    return [];
  }
}

function saveMru(ids) {
  try {
    localStorage.setItem(MRU_KEY, JSON.stringify(ids));
  } catch (_) { /* ignore quota errors */ }
}

function pushMru(stationId) {
  const id = parseInt(stationId, 10);
  if (!id) return;
  let mru = loadMru().filter(x => x !== id);
  mru.unshift(id);
  if (mru.length > MRU_MAX) mru = mru.slice(0, MRU_MAX);
  saveMru(mru);
}

// ── Station dropdown ─────────────────────────────────────────
function populateStations(stations) {
  state.stations = stations;
  dom.stationSelect.innerHTML = '';

  const placeholder = document.createElement('option');
  placeholder.value = '';
  placeholder.textContent = `— ${labels().stationLabel.replace(':', '')} —`;
  dom.stationSelect.appendChild(placeholder);

  // MRU section
  const mruIds = loadMru();
  const byId = new Map(stations.map(s => [s.id, s]));
  const mruStations = mruIds.map(id => byId.get(id)).filter(Boolean);

  if (mruStations.length > 0) {
    const mruLabel = state.lang === 'en' ? 'Recent' : 'Viimeisimmät';
    const allLabel = state.lang === 'en' ? 'All stations' : 'Kaikki asemat';
    const currentInMru = mruStations.some(s => s.id === state.currentStationId);

    const mruGroup = document.createElement('optgroup');
    mruGroup.label = mruLabel;
    for (const s of mruStations) {
      const opt = document.createElement('option');
      opt.value = s.id;
      opt.textContent = s.formatted_name;
      if (s.id === state.currentStationId) opt.selected = true;
      mruGroup.appendChild(opt);
    }
    dom.stationSelect.appendChild(mruGroup);

    const allGroup = document.createElement('optgroup');
    allGroup.label = allLabel;
    for (const s of stations) {
      const opt = document.createElement('option');
      opt.value = s.id;
      opt.textContent = s.formatted_name;
      if (!currentInMru && s.id === state.currentStationId) opt.selected = true;
      allGroup.appendChild(opt);
    }
    dom.stationSelect.appendChild(allGroup);
  } else {
    for (const s of stations) {
      const opt = document.createElement('option');
      opt.value = s.id;
      opt.textContent = s.formatted_name;
      if (s.id === state.currentStationId) opt.selected = true;
      dom.stationSelect.appendChild(opt);
    }
  }
}

// ── Event listeners ──────────────────────────────────────────
function initEvents() {
  dom.stationSelect.addEventListener('change', () => {
    const id = parseInt(dom.stationSelect.value, 10);
    if (!id) return;
    state.currentStationId = id;
    const opt = dom.stationSelect.options[dom.stationSelect.selectedIndex];
    saveSettings({ current_station_id: id, current_station_name: opt.textContent });
    fetchWeather(id);
  });

  dom.refreshBtn.addEventListener('click', () => {
    if (state.currentStationId) fetchWeather(state.currentStationId);
  });

  dom.langToggle.addEventListener('click', () => {
    state.lang = state.lang === 'fi' ? 'en' : 'fi';
    saveSettings({ language: state.lang });
    applyLabels();
    if (state.stations.length > 0) populateStations(state.stations);
    if (state.currentStationId) fetchWeather(state.currentStationId);
  });

  dom.carouselPrev.addEventListener('click', () => {
    if (carousel.index > 0) carouselGoTo(carousel.index - 1);
  });
  dom.carouselNext.addEventListener('click', () => {
    if (carousel.index < carousel.slides.length - 1) carouselGoTo(carousel.index + 1);
  });

  let touchStartX = 0;
  dom.carouselTrack.addEventListener('touchstart', e => { touchStartX = e.touches[0].clientX; }, { passive: true });
  dom.carouselTrack.addEventListener('touchend', e => {
    const dx = e.changedTouches[0].clientX - touchStartX;
    if (dx < -40 && carousel.index < carousel.slides.length - 1) carouselGoTo(carousel.index + 1);
    else if (dx > 40 && carousel.index > 0) carouselGoTo(carousel.index - 1);
  }, { passive: true });

  dom.settingsBtn.addEventListener('click', openSettings);
  dom.settingsClose.addEventListener('click', closeSettings);
  dom.settingsCancel.addEventListener('click', closeSettings);
  dom.settingsSave.addEventListener('click', onSettingsSave);

  dom.settingsModal.addEventListener('click', e => {
    if (e.target === dom.settingsModal) closeSettings();
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeSettings();
  });
}

/**
 * @brief Open the settings modal and populate current values.
 *
 * Loads the current API key and camera visibility settings into the modal form
 * before displaying it to the user.
 */
function openSettings() {
  dom.apiKeyInput.value = state.apiKey;
  dom.cameraToggle.checked = state.showCamera;
  setVisible(dom.settingsModal, true);
  dom.apiKeyInput.focus();
}

/**
 * @brief Close the settings modal.
 */
function closeSettings() {
  setVisible(dom.settingsModal, false);
}

/**
 * @brief Save settings from the modal form to the backend and apply changes.
 *
 * Persists the user's settings (API key and camera visibility) to the server
 * session, then fetches fresh weather data. Immediately hides the camera panel
 * if camera visibility was disabled.
 *
 * @details
 * - Saves openweathermap_api_key and show_camera to backend session
 * - Updates global state with new settings values
 * - Immediately hides camera panel if show_camera is disabled
 * - Triggers fetchWeather to refresh data (skips camera fetch if disabled)
 */
async function onSettingsSave() {
  const key = dom.apiKeyInput.value.trim();
  const showCamera = dom.cameraToggle.checked;
  state.apiKey = key;
  state.showCamera = showCamera;
  await saveSettings({ openweathermap_api_key: key, show_camera: showCamera });
  closeSettings();
  setVisible(dom.cameraPanel, showCamera);
  if (state.currentStationId) fetchWeather(state.currentStationId);
}

// ── Bootstrap ────────────────────────────────────────────────
async function init() {
  await fetchSettings();

  dom.apiKeyLabel = document.querySelector('.modal-body label');
  dom.cameraLabel = document.querySelector('.camera-setting label');
  applyLabels();
  initEvents();

  const stations = await fetchStations();
  if (stations.length === 0) return;

  populateStations(stations);

  // If no saved station, pick the first one
  if (!state.currentStationId && stations.length > 0) {
    state.currentStationId = stations[0].id;
    dom.stationSelect.value = stations[0].id;
  } else if (state.currentStationId) {
    dom.stationSelect.value = state.currentStationId;
  }

  if (state.currentStationId) {
    fetchWeather(state.currentStationId);
  }
}

document.addEventListener('DOMContentLoaded', init);
