'use strict';

import { state, forecastCarousel, FORECAST_PAGE_SIZE, loadMru } from './state.js';

// ── i18n label tables ───────────────────────────────────────
export const LABELS = {
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
    stationSearch: 'Search weather station',
    stationSearchPlaceholder: 'Type station name…',
    stationNoResults: 'No results',
    serviceError: 'Weather data service unavailable (error {code}). Retrying soon.',
    networkError: 'Network error. Check your connection.',
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
  },
};

// Weekday abbreviations indexed by Date.getDay() (0=Sun)
export const WEEKDAYS_FI = ['Su', 'Ma', 'Ti', 'Ke', 'To', 'Pe', 'La'];
export const WEEKDAYS_EN = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];
export const WEEKDAYS_SV = ['Sö', 'Må', 'Ti', 'On', 'To', 'Fr', 'Lö'];

export const LANG_FLAGS = { fi: 'fi-fi', sv: 'fi-se', en: 'fi-gb' };
export const LANG_NAMES = { fi: 'Suomi', sv: 'Svenska', en: 'English' };

// ── DOM refs ────────────────────────────────────────────────
const $ = id => document.getElementById(id);

export const dom = {
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

// ── Label / language helpers ────────────────────────────────
export function labels() {
  return LABELS[state.lang];
}

export function syncLangDropdown() {
  const flagClass = LANG_FLAGS[state.lang] || 'fi-fi';
  const flagEl = dom.langBtn.querySelector('.fi');
  flagEl.className = `fi ${flagClass}`;
  dom.langBtnLabel.textContent = LANG_NAMES[state.lang] || state.lang;
  dom.langOptions.forEach(opt => {
    opt.classList.toggle('selected', opt.dataset.value === state.lang);
  });
}

export function applyLabels() {
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

// ── DOM utilities ───────────────────────────────────────────
export function showError(msg) {
  dom.errorBanner.textContent = msg;
  dom.errorBanner.classList.remove('hidden');
}

export function hideError() {
  dom.errorBanner.classList.add('hidden');
}

export function setVisible(el, visible) {
  if (visible) el.classList.remove('hidden');
  else el.classList.add('hidden');
}

export function setText(el, value) {
  el.textContent = value || '';
}

export function esc(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

export const escapeHtml = esc;

// ── Weather rendering ───────────────────────────────────────
export function renderWeather(data) {
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

  // Present weather — label type comes from backend
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

export function forecastGoTo(i) {
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
    } else if (f.time && f.date) {
      // f.time is UTC (from FMI); convert to browser-local time for display.
      const slotUtc = new Date(`${f.date}T${f.time}:00Z`);
      const localHour = slotUtc.getHours();
      const localDay  = slotUtc.getDay();
      timeLabel = `${weekdays[localDay]} ${localHour}–${localHour + 3}`;
    } else if (f.time) {
      const startHour = parseInt(f.time.split(':')[0], 10);
      timeLabel = `${startHour}–${startHour + 3}`;
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

// ── Station dropdown ─────────────────────────────────────────
export function populateStations(stations) {
  state.stations = stations;
  dom.stationSelect.innerHTML = '';

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
/**
 * @param {Function} selectFn  Callback invoked with (id, name) when user picks a station.
 */
export function openStationSearch(selectFn) {
  const L = labels();
  dom.stationSearchTitle.textContent = L.stationSearch;
  dom.stationSearchInput.placeholder = L.stationSearchPlaceholder;
  dom.stationSearchInput.value = '';
  renderStationSearchResults(selectFn);
  dom.stationSearchModal.classList.remove('hidden');
  dom.stationSearchInput.focus();
}

export function closeStationSearch() {
  dom.stationSearchModal.classList.add('hidden');
}

/**
 * @param {Function} selectFn  Callback invoked with (id, name) when user picks a station.
 */
export function renderStationSearchResults(selectFn) {
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
      selectFn(s.id, s.formatted_name);
      closeStationSearch();
    };
    li.addEventListener('click', select);
    li.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') select(); });
    dom.stationSearchResults.appendChild(li);
  }
}

// ── Settings modal ───────────────────────────────────────────
export function openSettings() {
  dom.cameraToggle.checked = state.showCamera;
  dom.followLocationToggle.checked = state.followLocation;
  setVisible(dom.settingsModal, true);
}

export function closeSettings() {
  setVisible(dom.settingsModal, false);
}
