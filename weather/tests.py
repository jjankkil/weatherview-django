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

import datetime
from datetime import timezone as dt_timezone
from unittest.mock import patch, MagicMock

import requests as requests_lib
from django.test import SimpleTestCase, Client, override_settings
from django.core.cache import cache

from weather.services.helpers import ok_to_add_station
from weather.services.weather_service import WeatherService
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


def _mock_http_error_response(status_code):
    """@brief Build a mock requests.Response that raises HTTPError on raise_for_status().

    @param status_code HTTP status code of the simulated error response.
    @return MagicMock whose raise_for_status() raises requests.HTTPError.
    """
    resp = MagicMock()
    resp.status_code = status_code
    http_err = requests_lib.exceptions.HTTPError(response=resp)
    resp.raise_for_status = MagicMock(side_effect=http_err)
    return resp


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

    def test_weather_station_to_dict_english(self):
        """@brief to_dict(lang='en') returns English wind direction."""
        ws = WeatherStation()
        ws.parse(_STATION_DATA_PAYLOAD)
        d = ws.to_dict(lang="en")
        self.assertEqual(d["wind_direction"], "from S")

    def test_present_weather_no_sade_sensor(self):
        """@brief present_weather_localized() returns (False, '') when SADE sensor is absent."""
        ws = WeatherStation()
        ws.parse(_STATION_DATA_PAYLOAD)
        is_precip_fi, text_fi = ws.present_weather_localized("fi")
        is_precip_en, text_en = ws.present_weather_localized("en")
        self.assertFalse(is_precip_fi)
        self.assertEqual(text_fi, "")
        self.assertFalse(is_precip_en)
        self.assertEqual(text_en, "")

    def test_present_weather_dry(self):
        """@brief present_weather_localized() returns is_precipitation=False and translates 'Pouta' to 'Dry'."""
        payload = {**_STATION_DATA_PAYLOAD, "sensorValues": [
            {"id": 22, "stationId": 12345, "name": "SADE", "shortName": "Sade",
             "measuredTime": "2026-05-12T12:50:00Z", "value": 0.0,
             "sensorValueDescriptionFi": "Pouta"},
        ]}
        ws = WeatherStation()
        ws.parse(payload)
        is_precip_fi, text_fi = ws.present_weather_localized("fi")
        is_precip_en, text_en = ws.present_weather_localized("en")
        self.assertFalse(is_precip_fi)
        self.assertEqual(text_fi, "Pouta")
        self.assertFalse(is_precip_en)
        self.assertEqual(text_en, "Dry")

    def test_present_weather_precipitation(self):
        """@brief present_weather_localized() returns is_precipitation=True when value >= 1."""
        payload = {**_STATION_DATA_PAYLOAD, "sensorValues": [
            {"id": 22, "stationId": 12345, "name": "SADE", "shortName": "Sade",
             "measuredTime": "2026-05-12T12:50:00Z", "value": 2.0,
             "sensorValueDescriptionFi": "Kohtalainen"},
        ]}
        ws = WeatherStation()
        ws.parse(payload)
        is_precip_fi, text_fi = ws.present_weather_localized("fi")
        is_precip_en, text_en = ws.present_weather_localized("en")
        self.assertTrue(is_precip_fi)
        self.assertEqual(text_fi, "Kohtalainen")
        self.assertTrue(is_precip_en)
        self.assertEqual(text_en, "Moderate rain")

    def test_present_weather_snow(self):
        """@brief present_weather_localized() returns is_precipitation=True and translates snow/sleet."""
        payload = {**_STATION_DATA_PAYLOAD, "sensorValues": [
            {"id": 22, "stationId": 12345, "name": "SADE", "shortName": "Sade",
             "measuredTime": "2026-05-12T12:50:00Z", "value": 4.0,
             "sensorValueDescriptionFi": "Heikko lumi/räntä"},
        ]}
        ws = WeatherStation()
        ws.parse(payload)
        is_precip_en, text_en = ws.present_weather_localized("en")
        self.assertTrue(is_precip_en)
        self.assertEqual(text_en, "Light snow/sleet")

    def test_present_weather_unknown_fi_string_falls_back(self):
        """@brief present_weather_localized() falls back to Finnish text for unknown values."""
        payload = {**_STATION_DATA_PAYLOAD, "sensorValues": [
            {"id": 22, "stationId": 12345, "name": "SADE", "shortName": "Sade",
             "measuredTime": "2026-05-12T12:50:00Z", "value": 1.0,
             "sensorValueDescriptionFi": "Tuntematon"},
        ]}
        ws = WeatherStation()
        ws.parse(payload)
        _, text_en = ws.present_weather_localized("en")
        self.assertEqual(text_en, "Tuntematon")


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

        # POST update
        r = self._post(
            "/api/settings/save/",
            data='{"language": "en"}',
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"ok": True})

        r = self._get("/api/settings/")
        self.assertEqual(r.json()["language"], "en")

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

    @override_settings(OPENWEATHER_API_KEY="k")
    @patch("weather.services.weather_service.requests.get")
    def test_api_station_data_with_owm_key(self, mock_get):
        """@brief With an OWM key, station data response includes current_symbol and forecast list."""
        today_str = datetime.date.today().isoformat()
        owm_city = {"weather": [{"id": 800}]}
        owm_forecast = {
            "list": [
                {
                    "dt_txt": f"{today_str} 15:00:00",
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
        self.assertEqual(data["forecast"][0]["date"], today_str)
        self.assertEqual(data["forecast"][0]["symbol"], "☀")
        self.assertEqual(data["forecast"][0]["temperature"], "10 °C")

    @override_settings(OPENWEATHER_API_KEY="k")
    @patch("weather.services.weather_service.requests.get")
    def test_forecast_excludes_items_on_or_after_cutoff(self, mock_get):
        """@brief Forecast items on or after today+3 are excluded; items within 3 days are included."""
        today = datetime.date.today()
        within = today + datetime.timedelta(days=2)
        cutoff = today + datetime.timedelta(days=3)

        owm_city = {"weather": [{"id": 800}]}
        owm_forecast = {
            "list": [
                {
                    "dt_txt": f"{within.isoformat()} 09:00:00",
                    "main": {"temp": 283.15},
                    "weather": [{"id": 800}],
                },
                {
                    "dt_txt": f"{cutoff.isoformat()} 09:00:00",
                    "main": {"temp": 290.15},
                    "weather": [{"id": 500}],
                },
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
        self.assertEqual(len(data["forecast"]), 1)
        self.assertEqual(data["forecast"][0]["date"], within.isoformat())

    @override_settings(OPENWEATHER_API_KEY="k")
    @patch("weather.services.weather_service.requests.get")
    def test_forecast_item_includes_date_field(self, mock_get):
        """@brief Each forecast item contains a 'date' field with the ISO date string."""
        tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        owm_city = {"weather": [{"id": 800}]}
        owm_forecast = {
            "list": [
                {
                    "dt_txt": f"{tomorrow} 12:00:00",
                    "main": {"temp": 280.0},
                    "weather": [{"id": 801}],
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
        item = r.json()["forecast"][0]
        self.assertIn("date", item)
        self.assertEqual(item["date"], tomorrow)
        self.assertEqual(item["time"], "12:00")

    @override_settings(OPENWEATHER_API_KEY="k")
    @patch("weather.services.weather_service.requests.get")
    def test_forecast_skips_items_with_short_dt_txt(self, mock_get):
        """@brief Forecast items with a dt_txt shorter than 10 characters are silently skipped."""
        today_str = datetime.date.today().isoformat()
        owm_city = {"weather": [{"id": 800}]}
        owm_forecast = {
            "list": [
                {"dt_txt": "bad", "main": {"temp": 300.0}, "weather": [{"id": 800}]},
                {
                    "dt_txt": f"{today_str} 06:00:00",
                    "main": {"temp": 283.15},
                    "weather": [{"id": 800}],
                },
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
        self.assertEqual(len(r.json()["forecast"]), 1)

    @patch("weather.services.weather_service.requests.get")
    def test_api_nearest_station_returns_closest(self, mock_get):
        """@brief GET /api/nearest-station/ returns the station closest to the given coordinates."""
        mock_get.return_value = _mock_response(_STATION_LIST_PAYLOAD)
        # Station is at lat=65.0, lon=25.0 (from _STATION_LIST_PAYLOAD GeoJSON [lon, lat])
        r = self._get("/api/nearest-station/?lat=65.0&lon=25.0")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["id"], 12345)
        self.assertEqual(data["formatted_name"], "Oulu, Ritaharju vt4")

    def test_api_nearest_station_missing_params(self):
        """@brief GET /api/nearest-station/ without lat/lon returns HTTP 400."""
        r = self._get("/api/nearest-station/")
        self.assertEqual(r.status_code, 400)
        self.assertIn("error", r.json())

    def test_api_nearest_station_invalid_params(self):
        """@brief GET /api/nearest-station/ with non-numeric lat/lon returns HTTP 400."""
        r = self._get("/api/nearest-station/?lat=abc&lon=xyz")
        self.assertEqual(r.status_code, 400)

    @patch("weather.services.weather_service.requests.get")
    def test_api_station_data_upstream_503_returns_502_with_clean_message(self, mock_get):
        """@brief When Digitraffic returns 503, the station endpoint returns HTTP 502 with a clean error message."""
        mock_get.side_effect = [
            _mock_response(_STATION_LIST_PAYLOAD),      # station list succeeds
            _mock_http_error_response(503),             # station data: 503 from Digitraffic
        ]
        r = self._get("/api/station/12345/")
        self.assertEqual(r.status_code, 502)
        data = r.json()
        self.assertIn("error", data)
        self.assertIn("503", data["error"])
        self.assertNotIn("http", data["error"].lower().replace("http 503", ""))  # no raw URL

    @patch("weather.services.weather_service.requests.get")
    def test_api_station_data_upstream_500_returns_502_with_clean_message(self, mock_get):
        """@brief When Digitraffic returns 500, the station endpoint returns HTTP 502 with a clean error message."""
        mock_get.side_effect = [
            _mock_response(_STATION_LIST_PAYLOAD),
            _mock_http_error_response(500),
        ]
        r = self._get("/api/station/12345/")
        self.assertEqual(r.status_code, 502)
        data = r.json()
        self.assertIn("error", data)
        self.assertIn("500", data["error"])


class NextUpdateAtTests(SimpleTestCase):
    """@brief Unit tests for WeatherStation.next_update_at and seconds_until_next_update."""

    def _make_payload(self, ts: str) -> dict:
        return {**_STATION_DATA_PAYLOAD, "dataUpdatedTime": ts}

    def test_known_observation_time_returns_latest_plus_interval_plus_delay(self):
        """@brief next_update_at equals _latest_time + DEFAULT_POLLING_INTERVAL_S + STATION_UPDATE_DELAY_S."""
        from weather.services.definitions import Constants
        obs = datetime.datetime(2026, 5, 12, 12, 50, 0, tzinfo=dt_timezone.utc)
        ws = WeatherStation()
        ws.parse(self._make_payload("2026-05-12T12:50:00Z"))
        expected = obs + datetime.timedelta(
            seconds=Constants.DEFAULT_POLLING_INTERVAL_S + Constants.STATION_UPDATE_DELAY_S
        )
        self.assertEqual(ws.next_update_at, expected)

    def test_unknown_observation_time_returns_now_plus_default_interval(self):
        """@brief next_update_at falls back to now + DEFAULT_POLLING_INTERVAL_S when observation time is unknown."""
        from django.utils import timezone as dj_tz
        from weather.services.definitions import Constants
        ws = WeatherStation()  # _latest_time stays at epoch (year=1970)
        before = dj_tz.now()
        result = ws.next_update_at
        after = dj_tz.now()
        self.assertGreaterEqual(result, before + datetime.timedelta(seconds=Constants.DEFAULT_POLLING_INTERVAL_S))
        self.assertLessEqual(result, after + datetime.timedelta(seconds=Constants.DEFAULT_POLLING_INTERVAL_S + 1))

    def test_seconds_until_next_update_recent_observation(self):
        """@brief seconds_until_next_update returns DEFAULT_POLLING_INTERVAL_S + STATION_UPDATE_DELAY_S for a just-updated station."""
        from django.utils import timezone as dj_tz
        from weather.services.definitions import Constants
        now = dj_tz.now()
        ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        ws = WeatherStation()
        ws.parse(self._make_payload(ts))
        expected = Constants.DEFAULT_POLLING_INTERVAL_S + Constants.STATION_UPDATE_DELAY_S
        result = ws.seconds_until_next_update
        self.assertGreaterEqual(result, expected - 2)
        self.assertLessEqual(result, expected + 2)

    def test_seconds_until_next_update_clamps_to_zero_when_overdue(self):
        """@brief seconds_until_next_update returns 0 when next_update_at is in the past."""
        ws = WeatherStation()
        ws._latest_time = datetime.datetime(2020, 1, 1, 0, 0, 0, tzinfo=dt_timezone.utc)
        self.assertEqual(ws.seconds_until_next_update, 0)

    def test_seconds_until_next_update_clamps_to_600_max(self):
        """@brief seconds_until_next_update is clamped to 600 even when DEFAULT_POLLING_INTERVAL_S + STATION_UPDATE_DELAY_S would exceed it."""
        from weather.services.definitions import Constants
        # Temporarily make the sum exceed 600 by using a future obs time far ahead
        from django.utils import timezone as dj_tz
        future = dj_tz.now() + datetime.timedelta(seconds=700)
        ws = WeatherStation()
        ws._latest_time = future
        self.assertLessEqual(ws.seconds_until_next_update, 600)


class StationDataCacheTests(SimpleTestCase):
    """@brief Tests for per-station response caching in api_station_data."""

    def setUp(self):
        cache.clear()
        self.client = Client(enforce_csrf_checks=False)
        self._get = lambda path, **kw: self.client.get(path, secure=True, **kw)

    @patch("weather.services.weather_service.requests.get")
    def test_cached_response_served_without_second_digitraffic_request(self, mock_get):
        """@brief Second request within next_update_at window is served from cache; Digitraffic not called again."""
        mock_get.side_effect = [
            _mock_response(_STATION_LIST_PAYLOAD),
            _mock_response(_STATION_DATA_PAYLOAD),
        ]
        self._get("/api/station/12345/")
        # Cache is now populated. A second request should not call mock_get again.
        self._get("/api/station/12345/")
        # mock_get was called exactly twice (station list + station data), not four times.
        self.assertEqual(mock_get.call_count, 2)

    @patch("weather.services.weather_service.requests.get")
    def test_cache_bypassed_with_refresh_param(self, mock_get):
        """@brief ?refresh=1 bypasses the cache and fetches fresh data from Digitraffic."""
        mock_get.side_effect = [
            _mock_response(_STATION_LIST_PAYLOAD),
            _mock_response(_STATION_DATA_PAYLOAD),
        ]
        self._get("/api/station/12345/")          # populate cache (2 calls)
        mock_get.side_effect = [
            _mock_response(_STATION_DATA_PAYLOAD),
        ]
        r = self._get("/api/station/12345/?refresh=1")  # station list cached, only station data re-fetched
        self.assertEqual(r.status_code, 200)
        self.assertEqual(mock_get.call_count, 3)

    @patch("weather.services.weather_service.requests.get")
    def test_next_update_at_not_in_json_response(self, mock_get):
        """@brief The internal _next_update_at field is never exposed in the API response."""
        mock_get.side_effect = [
            _mock_response(_STATION_LIST_PAYLOAD),
            _mock_response(_STATION_DATA_PAYLOAD),
        ]
        r = self._get("/api/station/12345/")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_next_update_at", r.json())

    @patch("weather.services.weather_service.requests.get")
    def test_cached_response_also_omits_next_update_at(self, mock_get):
        """@brief _next_update_at is absent from the response even when served from cache."""
        mock_get.side_effect = [
            _mock_response(_STATION_LIST_PAYLOAD),
            _mock_response(_STATION_DATA_PAYLOAD),
        ]
        self._get("/api/station/12345/")           # populate cache
        mock_get.side_effect = []                  # no further calls allowed
        r = self._get("/api/station/12345/")       # served from cache
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_next_update_at", r.json())


class WeatherServiceErrorTests(SimpleTestCase):
    """@brief Unit tests for WeatherService._get() error message formatting."""

    @patch("weather.services.weather_service.requests.get")
    def test_get_503_produces_clean_error_message(self, mock_get):
        """@brief _get() on a 503 response sets a human-readable error, not a raw exception string."""
        mock_get.return_value = _mock_http_error_response(503)
        svc = WeatherService()
        result = svc._get("https://example.com/")
        self.assertEqual(result, {})
        self.assertTrue(svc.has_error)
        self.assertEqual(svc._status, 503)
        self.assertEqual(svc.error_message, "Upstream service error (HTTP 503)")

    @patch("weather.services.weather_service.requests.get")
    def test_get_500_produces_clean_error_message(self, mock_get):
        """@brief _get() on a 500 response sets a human-readable error."""
        mock_get.return_value = _mock_http_error_response(500)
        svc = WeatherService()
        svc._get("https://example.com/")
        self.assertEqual(svc.error_message, "Upstream service error (HTTP 500)")

    @patch("weather.services.weather_service.requests.get")
    def test_get_404_produces_clean_error_message(self, mock_get):
        """@brief _get() on a 404 response sets a human-readable error (not raw URL)."""
        mock_get.return_value = _mock_http_error_response(404)
        svc = WeatherService()
        svc._get("https://example.com/")
        self.assertTrue(svc.has_error)
        self.assertEqual(svc._status, 404)
        self.assertEqual(svc.error_message, "Upstream request failed (HTTP 404)")

    @patch("weather.services.weather_service.requests.get")
    def test_get_connection_error_preserved_as_string(self, mock_get):
        """@brief _get() on a connection error (no HTTP response) preserves the exception message."""
        mock_get.side_effect = requests_lib.exceptions.ConnectionError("Connection refused")
        svc = WeatherService()
        result = svc._get("https://example.com/")
        self.assertEqual(result, {})
        self.assertTrue(svc.has_error)
        self.assertEqual(svc._status, 0)
        self.assertIn("Connection refused", svc.error_message)
