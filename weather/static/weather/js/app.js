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
    save: 'Save',
    cancel: 'Cancel',
    langToggle: 'FI',
  },
};

// ── State ───────────────────────────────────────────────────
const state = {
  lang: 'fi',
  stations: [],
  currentStationId: null,
  apiKey: '',
  refreshTimer: null,
  countdownTimer: null,
  countdownValue: 0,
  loading: false,
};

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
  settingsSave:   $('settings-save'),
  settingsCancel: $('settings-cancel'),
  settingsClose:  $('settings-close'),
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
async function fetchSettings() {
  try {
    const r = await fetch('/api/settings/');
    if (!r.ok) return;
    const data = await r.json();
    if (data.language) state.lang = data.language;
    if (data.openweathermap_api_key) state.apiKey = data.openweathermap_api_key;
    if (data.current_station_id) state.currentStationId = data.current_station_id;
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

function openSettings() {
  dom.apiKeyInput.value = state.apiKey;
  setVisible(dom.settingsModal, true);
  dom.apiKeyInput.focus();
}

function closeSettings() {
  setVisible(dom.settingsModal, false);
}

async function onSettingsSave() {
  const key = dom.apiKeyInput.value.trim();
  state.apiKey = key;
  await saveSettings({ openweathermap_api_key: key });
  closeSettings();
  if (state.currentStationId) fetchWeather(state.currentStationId);
}

// ── Bootstrap ────────────────────────────────────────────────
async function init() {
  await fetchSettings();

  dom.apiKeyLabel = document.querySelector('.modal-body label');
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
