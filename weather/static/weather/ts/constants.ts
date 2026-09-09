/**
 * Frontend application constants and configuration values.
 * Centralizes all constant values used throughout the application.
 */

// -- MRU (Most Recently Used) stations ---------------------------------------
export const MRU_KEY = "wx_mru_stations";
export const MRU_MAX = 10;

// -- User geolocation cache ---------------------------------------------------
export const USER_LOCATION_KEY = "wx_user_location";

// -- Weathercam API -----------------------------------------------------------

/** Base URL for the Digitraffic weathercam station list API. */
export const CAMERA_STATIONS_URL =
  "https://tie.digitraffic.fi/api/weathercam/v1/stations";

/** Base URL for weathercam images; append {presetId}.jpg to get the image. */
export const CAMERA_IMAGE_BASE = "https://weathercam.digitraffic.fi/";

// -- Compass directions -------------------------------------------------------

/** Cardinal and intercardinal direction names in Finnish, clockwise from north. */
export const DIRECTIONS_FI = [
  "pohjoiseen",
  "koilliseen",
  "itään",
  "kaakkoon",
  "etelään",
  "lounaaseen",
  "länteen",
  "luoteeseen",
];

/** Cardinal and intercardinal direction names in English, clockwise from north. */
export const DIRECTIONS_EN = [
  "north",
  "northeast",
  "east",
  "southeast",
  "south",
  "southwest",
  "west",
  "northwest",
];

/** Cardinal and intercardinal direction names in Swedish, clockwise from north. */
export const DIRECTIONS_SV = [
  "norr",
  "nordost",
  "öst",
  "sydost",
  "söder",
  "sydväst",
  "väst",
  "nordväst",
];
