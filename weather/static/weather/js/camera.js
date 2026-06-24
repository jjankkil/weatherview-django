'use strict';

import { CAMERA_STATIONS_URL, CAMERA_IMAGE_BASE, DIRECTIONS_FI, DIRECTIONS_EN, DIRECTIONS_SV } from './constants.js';

// ── Module-level deps injected by init() ─────────────────────
let _state, _dom, _labels, _setVisible;

export function initCamera(state, dom, labels, setVisible) {
  _state = state;
  _dom = dom;
  _labels = labels;
  _setVisible = setVisible;
}

// ── Internal state ───────────────────────────────────────────
let cameraStations = null;

export const carousel = { index: 0, slides: [] };
export const lightbox = { index: 0 };

// ── Geometry helpers ─────────────────────────────────────────

function haversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function bearingDeg(lat1, lon1, lat2, lon2) {
  const toRad = x => x * Math.PI / 180;
  const dLon = toRad(lon2 - lon1);
  const y = Math.sin(dLon) * Math.cos(toRad(lat2));
  const x = Math.cos(toRad(lat1)) * Math.sin(toRad(lat2)) -
            Math.sin(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.cos(dLon);
  return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
}

function bearingLabel(deg, lang) {
  const dirs = lang === 'en' ? DIRECTIONS_EN : lang === 'sv' ? DIRECTIONS_SV : DIRECTIONS_FI;
  return dirs[Math.round(deg / 45) % 8];
}

function findNearestCamera(stations, lat, lon) {
  let best = null, bestDist = Infinity;
  for (const f of stations) {
    const [fLon, fLat] = f.geometry.coordinates;
    const d = haversineKm(lat, lon, fLat, fLon);
    if (d < bestDist) { bestDist = d; best = f; }
  }
  return best ? { feature: best, distanceKm: bestDist } : null;
}

// ── Camera station loading ───────────────────────────────────

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

// ── Carousel ─────────────────────────────────────────────────

export function carouselGoTo(i) {
  carousel.index = i;
  _dom.carouselTrack.style.transform = `translateX(-${i * 100}%)`;
  _dom.carouselPrev.disabled = i === 0;
  _dom.carouselNext.disabled = i === carousel.slides.length - 1;
  const slide = carousel.slides[i];
  if (slide) {
    const L = _labels();
    const now = new Date();
    const timeStr = now.toLocaleTimeString(_state.lang === 'en' ? 'en-GB' : _state.lang === 'sv' ? 'sv-SE' : 'fi-FI');
    const loadedStr = `${L.cameraLoaded} ${timeStr}`;
    _dom.cameraUpdated.textContent = slide.loaded
      ? (slide.presentationName ? `${loadedStr} · ${L.cameraDirection} ${slide.presentationName}` : loadedStr)
      : (slide.presentationName ? `${L.cameraDirection} ${slide.presentationName}` : '');
  }
}

function buildCarousel(presets, ts, startIndex = 0) {
  carousel.slides = presets.map(p => ({ ...p, loaded: false }));
  carousel.index = 0;
  _dom.carouselTrack.innerHTML = '';

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
      err.textContent = _labels().cameraImageUnavailable;
      loading.replaceWith(err);
    };
    img.src = imgUrl;
    _dom.carouselTrack.appendChild(slide);
  }

  _dom.carouselPrev.disabled = true;
  _dom.carouselNext.disabled = presets.length <= 1;
  _dom.carouselTrack.style.transform = 'translateX(0)';

  const first = presets[0];
  _dom.cameraUpdated.textContent = first?.presentationName
    ? `${_labels().cameraDirection} ${first.presentationName}`
    : '';

  const clampedIndex = Math.min(startIndex, presets.length - 1);
  if (clampedIndex > 0) carouselGoTo(clampedIndex);
}

// ── Lightbox ─────────────────────────────────────────────────

export function lightboxGoTo(i) {
  lightbox.index = i;
  const unit = _dom.lightbox.classList.contains('is-fullscreen') ? '%' : 'vw';
  _dom.lightboxTrack.style.transform = `translateX(-${i * 100}${unit})`;
  _dom.lightboxPrev.disabled = i === 0;
  _dom.lightboxNext.disabled = i === carousel.slides.length - 1;
}

export function openLightbox(startIndex) {
  _dom.lightboxTrack.innerHTML = '';
  const carouselImgs = _dom.carouselTrack.querySelectorAll('img');
  carousel.slides.forEach((slide, i) => {
    const div = document.createElement('div');
    div.className = 'lightbox-slide';
    const srcImg = carouselImgs[i];
    if (srcImg) {
      const img = new Image();
      img.src = srcImg.src;
      div.appendChild(img);
    }
    if (slide.presentationName) {
      const label = document.createElement('div');
      label.className = 'lightbox-slide-label';
      label.textContent = slide.presentationName;
      div.appendChild(label);
    }
    _dom.lightboxTrack.appendChild(div);
  });
  _dom.lightbox.classList.remove('hidden');
  document.body.style.overflow = 'hidden';
  lightboxGoTo(startIndex);
}

export function closeLightbox() {
  if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
  _dom.lightbox.classList.add('hidden');
  document.body.style.overflow = '';
}

// ── Public entry point ───────────────────────────────────────

/**
 * @brief Find the nearest weathercam to a weather station and display it in the carousel.
 */
export async function showCameraForStation(stationId) {
  const station = _state.stations.find(s => s.id === stationId);
  if (!station || station.lat == null || station.lon == null) return;

  const camStations = await loadCameraStations();
  if (!camStations || camStations.length === 0) return;

  const result = findNearestCamera(camStations, station.lat, station.lon);
  if (!result) return;

  const { feature, distanceKm } = result;

  const [camLon, camLat] = feature.geometry.coordinates;
  const bearing = bearingDeg(station.lat, station.lon, camLat, camLon);
  const dirLabel = bearingLabel(bearing, _state.lang);
  const distM = Math.round(distanceKm * 1000);
  const distLabel = distanceKm < 1
    ? `${distM} m ${dirLabel}`
    : `${distanceKm.toFixed(1)} km ${dirLabel}`;

  const rawName = feature.properties.name || feature.properties.id || '';
  _dom.cameraTitle.textContent = rawName.replace(/_/g, ' ');
  _dom.cameraDistance.textContent = distLabel;
  _dom.cameraUpdated.textContent = '';
  _setVisible(_dom.cameraPanel, true);

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
  const previousIndex = carousel.index;
  buildCarousel(presets, Date.now(), previousIndex);
}
