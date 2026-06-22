'use strict';

import { MRU_KEY, MRU_MAX } from './constants.js';
import {
  initCamera, showCameraForStation,
  carousel, lightbox,
  carouselGoTo, lightboxGoTo, openLightbox, closeLightbox,
} from './camera.js';

// ── i18n ────────────────────────────────────────────────────
const LABELS = {
  fi: {
    appTitle: 'Tiesää',
    stationLabel: 'Sääasema:',
    obsTime: 'Havaintoaika:',
    temperature: 'Lämpötila:',
    feelsLike: 'Tuntuu kuin:',
    tempChange: 'Lämpötilan muutos:',
    wind: 'Tuulen nopeus (ka.):',
    windDir: 'Tuulen suunta:',
    windMax: 'Maksimituuli:',
    humidity: 'Ilman kosteus:',
    dewPoint: 'Kastepiste:',
    roadTemp: 'Tien pintalämpötila:',
    visibility: 'Näkyvyys:',
    weather: 'Säätila:',
    precipitation: 'Sade:',
    forecastTitle: 'Ennuste',
    refresh: 'Päivitä nyt',
    loading: 'Ladataan…',
    loadingStations: '— Ladataan asemia… —',
    nextUpdate: 'Seuraava päivitys: {s} s',
    settingsTitle: 'Asetukset',
    cameraLabel: 'Näytä kelikameroiden kuvat:',
    followLocationLabel: 'Käytä sijaintiasi aseman valintaan:',
    cameraLoaded: 'Ladattu',
    cameraDirection: 'Suunta',
    cameraImageUnavailable: 'Kuva ei saatavilla',
    mruRecent: 'Viimeisimmät',
    mruAll: 'Kaikki asemat',
    save: 'Tallenna',
    cancel: 'Peruuta',
    stationSearch: 'Etsi sääasema',
    stationSearchPlaceholder: 'Kirjoita aseman nimi…',
    stationNoResults: 'Ei tuloksia',
    serviceError: 'Säätietopalvelu ei vastaa (virhe {code}). Yritetään uudelleen pian.',
    networkError: 'Verkkovirhe. Tarkista yhteytesi.',
  },
  en: {
    appTitle: 'Road Weather',
    stationLabel: 'Weather station:',
    obsTime: 'Observation time:',
    temperature: 'Temperature:',
    feelsLike: 'Feels like:',
    tempChange: 'Temperature change:',
    wind: 'Wind speed (avg):',
    windDir: 'Wind direction:',
    windMax: 'Max wind:',
    humidity: 'Humidity:',
    dewPoint: 'Dew point:',
    roadTemp: 'Road surface temp:',
    visibility: 'Visibility:',
    weather: 'Weather:',
    precipitation: 'Precipitation:',
    forecastTitle: 'Forecast',
    refresh: 'Refresh now',
    loading: 'Loading…',
    loadingStations: '— Loading stations… —',
    nextUpdate: 'Next update: {s} s',
    settingsTitle: 'Settings',
    cameraLabel: 'Show weather camera images:',
    followLocationLabel: 'Use my location to select station:',
    cameraLoaded: 'Loaded',
    cameraDirection: 'Direction',
    cameraImageUnavailable: 'Image unavailable',
    mruRecent: 'Recent',
    mruAll: 'All stations',
    save: 'Save',
    cancel: 'Cancel',
  },
  sv: {
    appTitle: 'Vägväder',
    stationLabel: 'Väderstation:',
    obsTime: 'Observationstid:',
    temperature: 'Temperatur:',
    feelsLike: 'Känns som:',
    tempChange: 'Temperaturändring:',
    wind: 'Vindhastighet (medelv.):',
    windDir: 'Vindriktning:',
    windMax: 'Maxvind:',
    humidity: 'Luftfuktighet:',
    dewPoint: 'Daggpunkt:',
    roadTemp: 'Vägytans temperatur:',
    visibility: 'Sikt:',
    weather: 'Väder:',
    precipitation: 'Nederbörd:',
    forecastTitle: 'Prognos',
    refresh: 'Uppdatera nu',
    loading: 'Laddar…',
    loadingStations: '— Laddar stationer… —',
    nextUpdate: 'Nästa uppdatering: {s} s',
    settingsTitle: 'Inställningar',
    cameraLabel: 'Visa vägkamerabilder:',
    followLocationLabel: 'Använd min plats för stationsval:',
    cameraLoaded: 'Laddad',
    cameraDirection: 'Riktning',
    cameraImageUnavailable: 'Bild ej tillgänglig',
    mruRecent: 'Senaste',
    mruAll: 'Alla stationer',
    save: 'Spara',
    cancel: 'Avbryt',
    stationSearch: 'Sök väderstation',
    stationSearchPlaceholder: 'Skriv stationens namn…',
    stationNoResults: 'Inga resultat',
    serviceError: 'Väderdatatjänsten svarar inte (fel {code}). Försöker igen snart.',
    networkError: 'Nätverksfel. Kontrollera din anslutning.',
    stationSearch: 'Search weather station',
    stationSearchPlaceholder: 'Type station name…',
    stationNoResults: 'No results',
    serviceError: 'Weather data service unavailable (error {code}). Retrying soon.',
    networkError: 'Network error. Check your connection.',
  },
};

// Weekday abbreviations indexed by Date.getDay() (0=Sun)
const WEEKDAYS_FI = ['Su', 'Ma', 'Ti', 'Ke', 'To', 'Pe', 'La'];
const WEEKDAYS_EN = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];
const WEEKDAYS_SV = ['Sö', 'Må', 'Ti', 'On', 'To', 'Fr', 'Lö'];

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
 * @property {?number} refreshDueAt Epoch ms when new data will be available (null if unknown).
 * @property {boolean} loading Whether a weather data fetch is currently in progress.
 */
const state = {
  lang: 'fi',
  stations: [],
  currentStationId: null,
  showCamera: true,
  followLocation: false,
  refreshTimer: null,
  countdownTimer: null,
  refreshDueAt: null,
  loading: false,
};

// ── Forecast carousel state ───────────────────────────────────
const forecastCarousel = { index: 0, items: [] };
const FORECAST_PAGE_SIZE = 3;

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
  dewPointLabel:  $('dew-point-label'),
  dewPointValue:  $('dew-point-value'),
  dewPointRow:    $('dew-point-row'),
  roadTempLabel:  $('road-temp-label'),
  roadTempValue:  $('road-temp-value'),
  roadTempRow:    $('road-temp-row'),
  visibilityLabel:$('visibility-label'),
  visibilityValue:$('visibility-value'),
  visibilityRow:  $('visibility-row'),
  pwLabel:        $('pw-label'),
  pwValue:        $('pw-value'),
  pwRow:          $('pw-row'),
  forecastSection:$('forecast-section'),
  forecastTitle:  $('forecast-title'),
  forecastItems:  $('forecast-items'),
  forecastPrev:   $('forecast-prev'),
  forecastNext:   $('forecast-next'),
  refreshBtn:     $('refresh-btn'),
  refreshLabel:   $('refresh-label'),
  nextUpdateLabel:$('next-update-label'),
  langDropdown:   $('lang-dropdown'),
  langBtn:        $('lang-btn'),
  langBtnLabel:   $('lang-btn').querySelector('.lang-btn-label'),
  langOptions:    $('lang-list').querySelectorAll('.lang-option'),
  settingsBtn:    $('settings-btn'),
  stationSearchBtn:     $('station-search-btn'),
  stationSearchModal:   $('station-search-modal'),
  stationSearchTitle:   $('station-search-title'),
  stationSearchInput:   $('station-search-input'),
  stationSearchResults: $('station-search-results'),
  stationSearchClose:   $('station-search-close'),
  settingsModal:  $('settings-modal'),
  settingsTitle:  $('settings-modal-title'),
  cameraToggle:        $('camera-toggle'),
  cameraLabel:         $('camera-label'),
  followLocationToggle: $('follow-location-toggle'),
  followLocationLabel:  $('follow-location-label'),
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
  lightbox:       $('camera-lightbox'),
  lightboxClose:      $('lightbox-close'),
  lightboxFullscreen: $('lightbox-fullscreen'),
  lightboxTrack:  $('lightbox-track'),
  lightboxPrev:   $('lightbox-prev'),
  lightboxNext:   $('lightbox-next'),
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
  state.refreshDueAt = null;
  dom.nextUpdateLabel.textContent = '';
}

function startNextUpdateDisplay(seconds) {
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

function labels() {
  return LABELS[state.lang];
}

const LANG_FLAGS = { fi: 'fi-fi', sv: 'fi-se', en: 'fi-gb' };
const LANG_NAMES = { fi: 'Suomi', sv: 'Svenska', en: 'English' };

function syncLangDropdown() {
  const flagClass = LANG_FLAGS[state.lang] || 'fi-fi';
  const flagEl = dom.langBtn.querySelector('.fi');
  flagEl.className = `fi ${flagClass}`;
  dom.langBtnLabel.textContent = LANG_NAMES[state.lang] || state.lang;
  dom.langOptions.forEach(opt => {
    opt.classList.toggle('selected', opt.dataset.value === state.lang);
  });
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
  setText(dom.dewPointLabel, L.dewPoint);
  setText(dom.roadTempLabel, L.roadTemp);
  setText(dom.visibilityLabel, L.visibility);
  setText(dom.forecastTitle, L.forecastTitle);
  setText(dom.refreshLabel, L.refresh);
  dom.stationSearchBtn.title = L.stationSearch;
  syncLangDropdown();
  setText(dom.cameraLabel, L.cameraLabel);
  setText(dom.followLocationLabel, L.followLocationLabel);
  setText(dom.settingsSave, L.save);
  setText(dom.settingsCancel, L.cancel);
  setText(dom.settingsTitle, L.settingsTitle);
  document.documentElement.lang = state.lang;
}

// ── API calls ────────────────────────────────────────────────
/**
 * @brief Fetch and apply user settings from the backend session.
 *
 * Retrieves user preferences (language, current station, camera visibility,
 * follow-location) from the server and updates the global state. Gracefully
 * handles network errors by silently ignoring failures and retaining current
 * state values.
 *
 * @return {Promise<void>} Always resolves (errors are ignored).
 * @details
 * - Updates state.lang with user's language preference
 * - Updates state.currentStationId with last selected station (null if not set)
 * - Updates state.showCamera with camera visibility preference (defaults to true)
 * - Updates state.followLocation with follow-location preference (defaults to false)
 * - Network errors are silently caught; state retains default values on failure
 */
async function fetchSettings() {
  try {
    const r = await fetch('/api/settings/');
    if (!r.ok) return;
    const data = await r.json();
    if (data.language) state.lang = data.language;
    if (data.current_station_id) state.currentStationId = data.current_station_id;
    if (data.show_camera !== undefined) state.showCamera = data.show_camera;
    if (data.follow_location !== undefined) state.followLocation = data.follow_location;
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

async function fetchWeather(stationId, fresh = false) {
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
    // Only load and display camera if user has enabled it in settings
    if (state.showCamera) showCameraForStation(stationId);
  } catch (e) {
    showError(labels().networkError);
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

  setVisible(dom.dewPointRow, !!data.dew_point);
  setText(dom.dewPointValue, data.dew_point);

  setVisible(dom.roadTempRow, !!data.road_temperature);
  setText(dom.roadTempValue, data.road_temperature);

  setVisible(dom.visibilityRow, !!data.visibility);
  setText(dom.visibilityValue, data.visibility);

  // Present weather - label type comes from backend
  const hasPW = !!data.present_weather;
  setVisible(dom.pwRow, hasPW);
  if (hasPW) {
    const L = labels();
    setText(dom.pwLabel, data.present_weather_is_precipitation ? L.precipitation : L.weather);
    setText(dom.pwValue, data.present_weather);
  }

  // Current weather symbol
  const hasSymbol = !!data.current_symbol;
  setVisible(dom.symbolRow, hasSymbol);
  setText(dom.currentSymbol, data.current_symbol);

  // Forecast
  forecastCarousel.items = data.forecast || [];
  forecastCarousel.index = 0;
  setVisible(dom.forecastSection, forecastCarousel.items.length > 0);
  forecastGoTo(0);

  setVisible(dom.weatherCard, true);
}

function esc(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

const escapeHtml = esc;

function forecastGoTo(i) {
  forecastCarousel.index = i;
  const items = forecastCarousel.items;
  const weekdays = state.lang === 'en' ? WEEKDAYS_EN : state.lang === 'sv' ? WEEKDAYS_SV : WEEKDAYS_FI;
  dom.forecastItems.innerHTML = '';
  const page = items.slice(i, i + FORECAST_PAGE_SIZE);
  for (const f of page) {
    let timeLabel = '';
    if (f.daily) {
      if (f.date) {
        const day = new Date(f.date + 'T00:00:00').getDay();
        timeLabel = weekdays[day];
      }
    } else if (f.time) {
      const startHour = parseInt(f.time.split(':')[0], 10);
      const range = `${startHour}–${startHour + 3}`;
      if (f.date) {
        const day = new Date(f.date + 'T00:00:00').getDay();
        timeLabel = `${weekdays[day]} ${range}`;
      } else {
        timeLabel = range;
      }
    }
    const item = document.createElement('div');
    item.className = f.daily ? 'forecast-item forecast-item--daily' : 'forecast-item';
    item.innerHTML = `
      <span class="forecast-time">${timeLabel}</span>
      <span class="forecast-symbol">${esc(f.symbol) || '—'}</span>
      <span class="forecast-temp">${esc(f.temperature)}</span>
    `;
    dom.forecastItems.appendChild(item);
  }
  dom.forecastPrev.disabled = i === 0;
  dom.forecastNext.disabled = i + FORECAST_PAGE_SIZE >= items.length;
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

  // MRU section
  const mruIds = loadMru();
  const byId = new Map(stations.map(s => [s.id, s]));
  const mruStations = mruIds.map(id => byId.get(id)).filter(Boolean);

  if (mruStations.length > 0) {
    const mruLabel = labels().mruRecent;
    const allLabel = labels().mruAll;
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

// ── Station search modal ─────────────────────────────────────
function openStationSearch() {
  const L = labels();
  dom.stationSearchTitle.textContent = L.stationSearch;
  dom.stationSearchInput.placeholder = L.stationSearchPlaceholder;
  dom.stationSearchInput.value = '';
  renderStationSearchResults();
  dom.stationSearchModal.classList.remove('hidden');
  dom.stationSearchInput.focus();
}

function closeStationSearch() {
  dom.stationSearchModal.classList.add('hidden');
}

function renderStationSearchResults() {
  const query = dom.stationSearchInput.value.trim().toLowerCase();
  const L = labels();
  dom.stationSearchResults.innerHTML = '';

  const matches = query
    ? state.stations.filter(s => s.formatted_name.toLowerCase().includes(query))
    : state.stations;

  if (matches.length === 0) {
    const li = document.createElement('li');
    li.className = 'search-no-results';
    li.textContent = L.stationNoResults;
    dom.stationSearchResults.appendChild(li);
    return;
  }

  for (const s of matches) {
    const li = document.createElement('li');
    li.tabIndex = 0;
    if (query) {
      const idx = s.formatted_name.toLowerCase().indexOf(query);
      li.innerHTML =
        escapeHtml(s.formatted_name.slice(0, idx)) +
        `<mark>${escapeHtml(s.formatted_name.slice(idx, idx + query.length))}</mark>` +
        escapeHtml(s.formatted_name.slice(idx + query.length));
    } else {
      li.textContent = s.formatted_name;
    }
    const select = () => {
      selectStation(s.id, s.formatted_name);
      closeStationSearch();
    };
    li.addEventListener('click', select);
    li.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') select(); });
    dom.stationSearchResults.appendChild(li);
  }
}

function selectStation(id, name) {
  state.currentStationId = id;
  saveSettings({ current_station_id: id, current_station_name: name });
  fetchWeather(id);
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

  dom.langBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    dom.langDropdown.classList.toggle('open');
    dom.langDropdown.setAttribute('aria-expanded', dom.langDropdown.classList.contains('open'));
  });

  dom.langOptions.forEach(opt => {
    opt.addEventListener('click', async () => {
      state.lang = opt.dataset.value;
      dom.langDropdown.classList.remove('open');
      dom.langDropdown.setAttribute('aria-expanded', 'false');
      await saveSettings({ language: state.lang });
      applyLabels();
      if (state.stations.length > 0) populateStations(state.stations);
      if (state.currentStationId) fetchWeather(state.currentStationId);
    });
  });

  document.addEventListener('click', (e) => {
    if (!dom.langDropdown.contains(e.target)) {
      dom.langDropdown.classList.remove('open');
      dom.langDropdown.setAttribute('aria-expanded', 'false');
    }
  });

  dom.forecastPrev.addEventListener('click', () => {
    if (forecastCarousel.index > 0) forecastGoTo(Math.max(0, forecastCarousel.index - FORECAST_PAGE_SIZE));
  });
  dom.forecastNext.addEventListener('click', () => {
    if (forecastCarousel.index + FORECAST_PAGE_SIZE < forecastCarousel.items.length)
      forecastGoTo(forecastCarousel.index + FORECAST_PAGE_SIZE);
  });

  dom.carouselPrev.addEventListener('click', () => {
    if (carousel.index > 0) carouselGoTo(carousel.index - 1);
  });
  dom.carouselNext.addEventListener('click', () => {
    if (carousel.index < carousel.slides.length - 1) carouselGoTo(carousel.index + 1);
  });

  dom.carouselTrack.addEventListener('click', e => {
    const img = e.target.closest('img');
    if (!img) return;
    const slide = img.closest('.carousel-slide');
    const slides = [...dom.carouselTrack.querySelectorAll('.carousel-slide')];
    const idx = slides.indexOf(slide);
    openLightbox(idx >= 0 ? idx : carousel.index);
  });

  dom.lightboxClose.addEventListener('click', closeLightbox);
  dom.lightbox.addEventListener('click', e => {
    if (e.target === dom.lightbox) closeLightbox();
  });
  dom.lightboxFullscreen.addEventListener('click', () => {
    if (!document.fullscreenElement) {
      dom.lightbox.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen().catch(() => {});
    }
  });
  document.addEventListener('fullscreenchange', () => {
    const isFs = !!document.fullscreenElement;
    dom.lightboxFullscreen.innerHTML = isFs ? '&#x2715;' : '&#x26F6;';
    dom.lightboxFullscreen.setAttribute('aria-label', isFs ? 'Exit fullscreen' : 'Toggle fullscreen');
    dom.lightbox.classList.toggle('is-fullscreen', isFs);
    if (isFs) {
      const w = screen.width;
      const h = screen.height;
      dom.lightboxTrack.style.setProperty('--fs-w', `${w}px`);
      dom.lightboxTrack.style.setProperty('--fs-h', `${h}px`);
      dom.lightbox.style.setProperty('--fs-w', `${w}px`);
      dom.lightbox.style.setProperty('--fs-h', `${h}px`);
    } else {
      dom.lightbox.style.removeProperty('--fs-w');
      dom.lightbox.style.removeProperty('--fs-h');
    }
    lightboxGoTo(lightbox.index);
  });
  dom.lightboxPrev.addEventListener('click', () => {
    if (lightbox.index > 0) lightboxGoTo(lightbox.index - 1);
  });
  dom.lightboxNext.addEventListener('click', () => {
    if (lightbox.index < carousel.slides.length - 1) lightboxGoTo(lightbox.index + 1);
  });

  let lightboxTouchX = 0;
  dom.lightboxTrack.addEventListener('touchstart', e => { lightboxTouchX = e.touches[0].clientX; }, { passive: true });
  dom.lightboxTrack.addEventListener('touchend', e => {
    const dx = e.changedTouches[0].clientX - lightboxTouchX;
    if (dx < -40 && lightbox.index < carousel.slides.length - 1) lightboxGoTo(lightbox.index + 1);
    else if (dx > 40 && lightbox.index > 0) lightboxGoTo(lightbox.index - 1);
  }, { passive: true });

  let touchStartX = 0;
  dom.carouselTrack.addEventListener('touchstart', e => { touchStartX = e.touches[0].clientX; }, { passive: true });
  dom.carouselTrack.addEventListener('touchend', e => {
    const dx = e.changedTouches[0].clientX - touchStartX;
    if (dx < -40 && carousel.index < carousel.slides.length - 1) carouselGoTo(carousel.index + 1);
    else if (dx > 40 && carousel.index > 0) carouselGoTo(carousel.index - 1);
  }, { passive: true });

  dom.stationSearchBtn.addEventListener('click', openStationSearch);
  dom.stationSearchClose.addEventListener('click', closeStationSearch);
  dom.stationSearchModal.addEventListener('click', e => {
    if (e.target === dom.stationSearchModal) closeStationSearch();
  });
  dom.stationSearchInput.addEventListener('input', renderStationSearchResults);

  dom.settingsBtn.addEventListener('click', openSettings);
  dom.settingsClose.addEventListener('click', closeSettings);
  dom.settingsCancel.addEventListener('click', closeSettings);
  dom.settingsSave.addEventListener('click', onSettingsSave);

  dom.settingsModal.addEventListener('click', e => {
    if (e.target === dom.settingsModal) closeSettings();
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      if (!dom.lightbox.classList.contains('hidden')) closeLightbox();
      else if (!dom.stationSearchModal.classList.contains('hidden')) closeStationSearch();
      else closeSettings();
    }
    if (e.key === 'ArrowLeft' && !dom.lightbox.classList.contains('hidden')) {
      if (lightbox.index > 0) lightboxGoTo(lightbox.index - 1);
    }
    if (e.key === 'ArrowRight' && !dom.lightbox.classList.contains('hidden')) {
      if (lightbox.index < carousel.slides.length - 1) lightboxGoTo(lightbox.index + 1);
    }
  });
}

/**
 * @brief Open the settings modal and populate current values.
 *
 * Loads the current camera visibility and follow-location settings into the
 * modal form before displaying it to the user.
 */
function openSettings() {
  dom.cameraToggle.checked = state.showCamera;
  dom.followLocationToggle.checked = state.followLocation;
  setVisible(dom.settingsModal, true);
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
 * Persists the user's settings (camera visibility and follow-location) to the
 * server session, then fetches fresh weather data or triggers geolocation.
 *
 * @details
 * - Saves show_camera and follow_location to backend session
 * - Updates global state with new settings values
 * - Immediately hides camera panel if show_camera is disabled
 * - If follow_location is enabled, calls selectNearestByGeolocation; otherwise
 *   triggers fetchWeather for the current station
 */
async function onSettingsSave() {
  const showCamera = dom.cameraToggle.checked;
  const followLocation = dom.followLocationToggle.checked;
  state.showCamera = showCamera;
  state.followLocation = followLocation;
  await saveSettings({ show_camera: showCamera, follow_location: followLocation });
  closeSettings();
  setVisible(dom.cameraPanel, showCamera);
  if (followLocation) {
    await selectNearestByGeolocation(state.stations);
  } else if (state.currentStationId) {
    fetchWeather(state.currentStationId);
  }
}

// ── Geolocation ──────────────────────────────────────────────

/**
 * @brief Select the nearest weather station using the browser Geolocation API.
 *
 * Called on page load when `state.followLocation` is true (user has enabled
 * "Use my location" in Settings) or when no station has been saved yet.
 * Obtains the device position via `navigator.geolocation.getCurrentPosition`,
 * then POSTs the coordinates to `/api/nearest-station/` to find the closest
 * FMI station by haversine distance.
 *
 * Falls back to `stations[0]` (the first alphabetically sorted station) and
 * logs a `console.warn` with a timestamp if:
 * - the browser does not support the Geolocation API,
 * - the user denies the permission prompt,
 * - the position is not obtained within the 8-second timeout, or
 * - the `/api/nearest-station/` request fails.
 *
 * @note The Geolocation API is only available in secure contexts (HTTPS or
 *       localhost). On plain HTTP the API is unavailable and the fallback fires
 *       immediately with "A Geolocation request can only be fulfilled in a
 *       secure context."
 *
 * @param {Array} stations Full station list already fetched from `/api/stations/`.
 */
async function selectNearestByGeolocation(stations) {
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
    const r = await fetch(`/api/nearest-station/?lat=${latitude}&lon=${longitude}`);
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

// ── Bootstrap ────────────────────────────────────────────────
async function init() {
  await fetchSettings();
  initCamera(state, dom, labels, setVisible);
  applyLabels();
  initEvents();

  const stations = await fetchStations();
  if (stations.length === 0) return;

  populateStations(stations);

  if (state.followLocation) {
    await selectNearestByGeolocation(stations);
  } else if (state.currentStationId) {
    dom.stationSelect.value = String(state.currentStationId);
    fetchWeather(state.currentStationId);
  } else {
    await selectNearestByGeolocation(stations);
  }
}

document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    clearInterval(state.countdownTimer);
    clearTimeout(state.refreshTimer);
    state.countdownTimer = null;
    state.refreshTimer = null;
    dom.nextUpdateLabel.textContent = '';
  } else if (state.refreshDueAt !== null) {
    const remaining = Math.ceil((state.refreshDueAt - Date.now()) / 1000);
    if (remaining <= 0) {
      state.refreshDueAt = null;
      if (state.currentStationId) fetchWeather(state.currentStationId, true);
    } else {
      dom.nextUpdateLabel.textContent = labels().nextUpdate.replace('{s}', remaining);
      state.countdownTimer = setInterval(() => {
        const r = Math.ceil((state.refreshDueAt - Date.now()) / 1000);
        if (r <= 0) {
          clearInterval(state.countdownTimer);
          state.countdownTimer = null;
          dom.nextUpdateLabel.textContent = '';
        } else {
          dom.nextUpdateLabel.textContent = labels().nextUpdate.replace('{s}', r);
        }
      }, 1000);
      state.refreshTimer = setTimeout(() => {
        if (state.currentStationId) fetchWeather(state.currentStationId, true);
      }, remaining * 1000);
    }
  }
});

document.addEventListener('DOMContentLoaded', init);
