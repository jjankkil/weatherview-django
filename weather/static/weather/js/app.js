'use strict';

import {
  initCamera,
  carousel, lightbox,
  carouselGoTo, lightboxGoTo, openLightbox, closeLightbox,
} from './camera.js';
import { state, forecastCarousel, FORECAST_PAGE_SIZE } from './state.js';
import {
  dom, labels, applyLabels, setVisible,
  openSettings, closeSettings,
  openStationSearch, closeStationSearch, renderStationSearchResults,
  populateStations, forecastGoTo,
} from './render.js';
import {
  fetchSettings, saveSettings, fetchStations, fetchWeather,
  clearCountdown, startNextUpdateDisplay,
} from './api.js';
import { selectNearestByGeolocation } from './geo.js';

// ── Station selection ────────────────────────────────────────
function selectStation(id, name) {
  state.currentStationId = id;
  saveSettings({ current_station_id: id, current_station_name: name });
  fetchWeather(id);
}

// ── Settings save handler ────────────────────────────────────
/**
 * @brief Save settings from the modal form to the backend and apply changes.
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

// ── Event wiring ─────────────────────────────────────────────
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

  dom.stationSearchBtn.addEventListener('click', () => openStationSearch(selectStation));
  dom.stationSearchClose.addEventListener('click', closeStationSearch);
  dom.stationSearchModal.addEventListener('click', e => {
    if (e.target === dom.stationSearchModal) closeStationSearch();
  });
  dom.stationSearchInput.addEventListener('input', () => renderStationSearchResults(selectStation));

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

// ── Cookie consent banner ────────────────────────────────────
const _CONSENT_KEY = 'cookie_consent_v1';

function initCookieBanner() {
  if (!dom.cookieBanner) return;
  if (localStorage.getItem(_CONSENT_KEY)) return;
  dom.cookieBanner.classList.remove('hidden');
  dom.cookieBannerOk.addEventListener('click', () => {
    localStorage.setItem(_CONSENT_KEY, '1');
    dom.cookieBanner.classList.add('hidden');
  }, { once: true });
}

// ── Bootstrap ────────────────────────────────────────────────
async function init() {
  await fetchSettings();
  initCamera(state, dom, labels, setVisible);
  applyLabels();
  initCookieBanner();
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

// ── Visibility-change: pause/resume countdown on tab switch ──
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
      startNextUpdateDisplay(remaining);
    }
  }
});

document.addEventListener('DOMContentLoaded', init);
