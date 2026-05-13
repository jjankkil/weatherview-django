'use strict';

/**
 * Frontend application constants and configuration values.
 * Centralizes all constant values used throughout the application.
 */

// ── MRU (Most Recently Used) stations ────────────────────────
const MRU_KEY = 'wx_mru_stations';  //!< localStorage key for MRU station list
const MRU_MAX = 10;                 //!< Maximum number of stations in MRU list

// ── Weathercam API ───────────────────────────────────────────

/** @brief Base URL for the Digitraffic weathercam station list API. */
const CAMERA_STATIONS_URL = 'https://tie.digitraffic.fi/api/weathercam/v1/stations';

/** @brief Base URL for weathercam images; append {presetId}.jpg to get the image. */
const CAMERA_IMAGE_BASE = 'https://weathercam.digitraffic.fi/';

// ── Compass directions ───────────────────────────────────────

/** @brief Cardinal and intercardinal direction names in Finnish, clockwise from north. */
const DIRECTIONS_FI = ['pohjoiseen','koilliseen','itään','kaakkoon','etelään','lounaaseen','länteen','luoteeseen'];

/** @brief Cardinal and intercardinal direction names in English, clockwise from north. */
const DIRECTIONS_EN = ['north','northeast','east','southeast','south','southwest','west','northwest'];
