## @file tests.py
#  @brief Django offline unit tests for the weather application.
#
#  All outbound HTTP calls are mocked so the suite runs without network access.
#  The live counterpart is in scripts/smoke_test.py.
#
#  Run with:
#  @code
#      python manage.py test weather
#  @endcode
#
#  @author Jari Jankkila
#  @date 2026

"""Django smoke tests for the weather app.

Run with:
    python manage.py test weather

These tests mock outbound HTTP so they run offline. The live counterpart
that actually hits Digitraffic + OpenWeatherMap is in
`scripts/smoke_test.py`.
"""

from unittest.mock import patch, MagicMock

from django.test import SimpleTestCase, Client
from django.core.cache import cache

from weather.services.helpers import ok_to_add_station
from weather.services.physics import fmi_feels_like_temperature
from weather.services.ui_helpers import (
    get_weather_symbol,
    wind_direction_as_text,
    format_station_name,
    get_station_city,
)
from weather.services.station_info import WeatherStationList
from weather.services.weather_station import WeatherStation


# ── Sample API payloads ─────────────────────────────────────
_STATION_FEATURE = {
    "type": "Feature",
    "id": 12345,
    "geometry": {"type": "Point", "coordinates": [25.0, 65.0, 0.0]},
    "properties": {
        "name": "vt4_Oulu_Ritaharju",
        "collectionStatus": "GATHERING",
        "dataUpdatedTime": "2026-05-12T12:00:00Z",
    },
}

_STATION_LIST_PAYLOAD = {
    "features": [
        _STATION_FEATURE,
        {  # filtered out by helpers (Test station)
            "type": "Feature",
            "id": 99999,
            "geometry": {"type": "Point", "coordinates": [0.0, 0.0, 0.0]},
            "properties": {
                "name": "Test_LAM_99999",
                "collectionStatus": "GATHERING",
                "dataUpdatedTime": "2026-05-12T12:00:00Z",
            },
        },
    ]
}

_STATION_DATA_PAYLOAD = {
    "id": 12345,
    "dataUpdatedTime": "2026-05-12T12:50:00Z",
    "sensorValues": [
        {
            "id": 1,
            "stationId": 12345,
            "name": "ILMA",
            "shortName": "Ilma",
            "measuredTime": "2026-05-12T12:50:00Z",
            "value": 10.7,
            "unit": "°C",
        },
        {
            "id": 2,
            "stationId": 12345,
            "name": "ILMAN_KOSTEUS",
            "shortName": "RH",
            "measuredTime": "2026-05-12T12:50:00Z",
            "value": 71.0,
            "unit": "%",
        },
        {
            "id": 3,
            "stationId": 12345,
            "name": "KESKITUULI",
            "shortName": "Tuuli",
            "measuredTime": "2026-05-12T12:50:00Z",
            "value": 4.1,
            "unit": "m/s",
        },
        {
            "id": 4,
            "stationId": 12345,
            "name": "TUULENSUUNTA",
            "shortName": "Suunta",
            "measuredTime": "2026-05-12T12:50:00Z",
            "value": 180,
            "unit": "°",
        },
        {
            "id": 58,
            "stationId": 12345,
            "name": "NÄKYVYYS_M",
            "shortName": "Nak",
            "measuredTime": "2026-05-12T12:50:00Z",
            "value": 20000,
            "unit": "m",
        },
    ],
}


def _mock_response(json_data, status_code=200):
    """@brief Build a mock requests.Response object.

    @param json_data   Python object returned by `.json()`.
    @param status_code HTTP status code (default 200).
    @return MagicMock that mimics a `requests.Response`.
    """
    m = MagicMock()
    m.status_code = status_code
    m.json.return_value = json_data
    m.raise_for_status = MagicMock()
    return m


# ── Pure helpers ────────────────────────────────────────────
class HelpersTests(SimpleTestCase):
    """@brief Tests for pure helper and UI utility functions."""

    def test_ok_to_add_station_filters_test_names(self):
        """@brief ok_to_add_station() accepts real stations and rejects test/empty names."""
        self.assertTrue(ok_to_add_station("vt4_Oulu_Ritaharju"))
        self.assertFalse(ok_to_add_station("Test_LAM_99999"))
        self.assertFalse(ok_to_add_station(""))

    def test_format_station_name(self):
        """@brief format_station_name() converts raw Digitraffic names to human-readable form."""
        self.assertEqual(
            format_station_name("vt4_Oulu_Ritaharju"),
            "Oulu, Ritaharju vt4",
        )
        self.assertEqual(format_station_name(""), "")

    def test_get_station_city(self):
        """@brief get_station_city() extracts the city part before the comma."""
        self.assertEqual(get_station_city("Oulu, Ritaharju vt4"), "Oulu")
        self.assertEqual(get_station_city("no-comma"), "")
        self.assertEqual(get_station_city(""), "")

    def test_wind_direction_as_text_fi_en(self):
        """@brief wind_direction_as_text() returns correct Finnish and English strings."""
        self.assertEqual(wind_direction_as_text(180, "fi"), "etelästä")
        self.assertEqual(wind_direction_as_text(180, "en"), "from S")
        self.assertEqual(wind_direction_as_text(None), "")

    def test_weather_symbol_mapping(self):
        """@brief get_weather_symbol() maps OpenWeatherMap condition IDs to Unicode symbols."""
        self.assertEqual(get_weather_symbol(800), "☀")
        self.assertEqual(get_weather_symbol(500), "🌧")
        self.assertEqual(get_weather_symbol(0), "")


class PhysicsTests(SimpleTestCase):
    """@brief Tests for FMI feels-like temperature physics calculations."""

    def test_feels_like_cold(self):
        """@brief Wind-chill branch: cold temperature with wind produces a lower feels-like value."""
        # cold + wind -> wind-chill branch
        val = fmi_feels_like_temperature(wind=5.0, rh=80.0, temp=-5.0)
        self.assertIsInstance(val, float)
        self.assertLess(val, -5.0)

    def test_feels_like_warm(self):
        """@brief Simmer branch: warm temperature with high humidity returns a float result."""
        # warm + humid -> simmer branch
        val = fmi_feels_like_temperature(wind=2.0, rh=80.0, temp=25.0)
        self.assertIsInstance(val, float)


# ── Model parsing ───────────────────────────────────────────
class ModelParsingTests(SimpleTestCase):
    """@brief Tests for WeatherStationList and WeatherStation model parsing."""

    def test_station_list_parse_and_sort(self):
        """@brief parse() ingests GeoJSON features and filters out test stations; sort_by_name() orders the result."""
        sl = WeatherStationList()
        self.assertTrue(sl.parse(_STATION_LIST_PAYLOAD["features"]))
        sl.sort_by_name()
        names = sl.get_name_list()
        # the Test_LAM_99999 entry should have been filtered out
        self.assertEqual(len(names), 1)
        self.assertEqual(names[0]["formatted_name"], "Oulu, Ritaharju vt4")

    def test_weather_station_parse_and_derived_fields(self):
        """@brief WeatherStation.parse() reads sensor values and derives visibility_str correctly."""
        ws = WeatherStation()
        self.assertTrue(ws.parse(_STATION_DATA_PAYLOAD))
        self.assertAlmostEqual(ws.air_temperature, 10.7)
        self.assertAlmostEqual(ws.air_humidity, 71.0)
        self.assertAlmostEqual(ws.wind_speed, 4.1)
        self.assertEqual(ws.wind_direction, 180)
        self.assertEqual(ws.visibility_str, "20 km")

    def test_weather_station_to_dict(self):
        """@brief to_dict() serialises sensor data including localised wind direction string."""
        ws = WeatherStation()
        ws.parse(_STATION_DATA_PAYLOAD)
        d = ws.to_dict(lang="fi")
        self.assertEqual(d["temperature_raw"], 10.7)
        self.assertEqual(d["wind_speed_raw"], 4.1)
        self.assertEqual(d["wind_direction"], "etelästä")
        self.assertEqual(d["visibility"], "20 km")


# ── View / API endpoints ────────────────────────────────────
class ViewTests(SimpleTestCase):
    """@brief Integration tests for the Django view / REST API endpoints."""

    def setUp(self):
        """@brief Reset the in-process cache and create a fresh HTTPS test client before each test."""
        cache.clear()
        # secure=True makes the test client send requests as HTTPS, satisfying
        # SECURE_SSL_REDIRECT which is active whenever DEBUG=False.
        self.client = Client(enforce_csrf_checks=False)
        self._get = lambda path, **kw: self.client.get(path, secure=True, **kw)
        self._post = lambda path, **kw: self.client.post(path, secure=True, **kw)

    def test_index_renders(self):
        """@brief GET / returns HTTP 200 and the application title."""
        r = self._get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Ties", r.content)  # "Tiesää" — UTF-8 prefix is enough

    def test_settings_default_and_save(self):
        """@brief GET /api/settings/ returns defaults; POST /api/settings/save/ persists new values."""
        r = self._get("/api/settings/")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["language"], "fi")
        self.assertEqual(data["openweathermap_api_key"], "")

        # POST update
        r = self._post(
            "/api/settings/save/",
            data='{"language": "en", "openweathermap_api_key": "test-key"}',
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"ok": True})

        r = self._get("/api/settings/")
        self.assertEqual(r.json()["language"], "en")
        self.assertEqual(r.json()["openweathermap_api_key"], "test-key")

    def test_settings_save_rejects_bad_json(self):
        """@brief POST /api/settings/save/ with malformed JSON returns HTTP 400."""
        r = self._post(
            "/api/settings/save/",
            data="not json",
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)

    @patch("weather.services.weather_service.requests.get")
    def test_api_stations_uses_digitraffic(self, mock_get):
        """@brief GET /api/stations/ returns filtered station list from mocked Digitraffic response."""
        mock_get.return_value = _mock_response(_STATION_LIST_PAYLOAD)
        r = self._get("/api/stations/")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data["stations"]), 1)
        self.assertEqual(data["stations"][0]["formatted_name"], "Oulu, Ritaharju vt4")

    @patch("weather.services.weather_service.requests.get")
    def test_api_station_data_without_api_key(self, mock_get):
        """@brief Without an OWM key, station data response omits symbol and forecast."""
        # First call: station list; second call: station data
        mock_get.side_effect = [
            _mock_response(_STATION_LIST_PAYLOAD),
            _mock_response(_STATION_DATA_PAYLOAD),
        ]
        r = self._get("/api/station/12345/")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["station_id"], 12345)
        self.assertEqual(data["station_name"], "Oulu, Ritaharju vt4")
        self.assertEqual(data["temperature_raw"], 10.7)
        # No API key -> no symbol, no forecast
        self.assertEqual(data["current_symbol"], "")
        self.assertEqual(data["forecast"], [])

    @patch("weather.services.weather_service.requests.get")
    def test_api_station_data_unknown_id(self, mock_get):
        """@brief Requesting a station id not present in the station list returns HTTP 502."""
        mock_get.return_value = _mock_response(_STATION_LIST_PAYLOAD)
        r = self._get("/api/station/77777/")
        self.assertEqual(r.status_code, 502)
        self.assertIn("error", r.json())

    @patch("weather.services.weather_service.requests.get")
    def test_api_station_data_with_owm_key(self, mock_get):
        """@brief With an OWM key, station data response includes current_symbol and forecast list."""
        # Pre-set API key via the real save endpoint (signed-cookie sessions
        # cannot be manipulated through self.client.session directly).
        r = self._post(
            "/api/settings/save/",
            data='{"openweathermap_api_key": "k", "language": "fi"}',
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)

        owm_city = {"weather": [{"id": 800}]}
        owm_forecast = {
            "list": [
                {
                    "dt_txt": "2026-05-12 15:00:00",
                    "main": {"temp": 283.15},
                    "weather": [{"id": 800}],
                }
            ]
        }
        mock_get.side_effect = [
            _mock_response(_STATION_LIST_PAYLOAD),
            _mock_response(_STATION_DATA_PAYLOAD),
            _mock_response(owm_city),
            _mock_response(owm_forecast),
        ]

        r = self._get("/api/station/12345/")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["current_symbol"], "☀")
        self.assertEqual(len(data["forecast"]), 1)
        self.assertEqual(data["forecast"][0]["time"], "15:00")
        self.assertEqual(data["forecast"][0]["symbol"], "☀")
        self.assertEqual(data["forecast"][0]["temperature"], "10 °C")
