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
that actually hits Digitraffic and the FMI open data WFS is in
`scripts/smoke_test.py`.
"""

import datetime
import json
from datetime import timezone as dt_timezone
from unittest.mock import MagicMock, patch

import requests as requests_lib
from django.core.cache import cache
from django.test import Client, SimpleTestCase, override_settings

from weather.services.fmi_symbols import get_fmi_weather_symbol
from weather.services.helpers import ok_to_add_station
from weather.services.physics import fmi_feels_like_temperature
from weather.services.station_info import WeatherStationList
from weather.services.ui_helpers import (format_station_name,
                                         wind_direction_as_text)
from weather.services.weather_service import WeatherService
from weather.services.weather_station import WeatherStation

# ── FMI WFS XML fixtures ────────────────────────────────────
_FMI_HOURLY_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0"
                       xmlns:BsWfs="http://xml.fmi.fi/schema/wfs/2.0">
  <wfs:member>
    <BsWfs:BsWfsElement>
      <BsWfs:Time>2099-12-31T21:00:00Z</BsWfs:Time>
      <BsWfs:ParameterName>Temperature</BsWfs:ParameterName>
      <BsWfs:ParameterValue>15.5</BsWfs:ParameterValue>
    </BsWfs:BsWfsElement>
  </wfs:member>
  <wfs:member>
    <BsWfs:BsWfsElement>
      <BsWfs:Time>2099-12-31T21:00:00Z</BsWfs:Time>
      <BsWfs:ParameterName>WeatherSymbol3</BsWfs:ParameterName>
      <BsWfs:ParameterValue>1</BsWfs:ParameterValue>
    </BsWfs:BsWfsElement>
  </wfs:member>
</wfs:FeatureCollection>"""

_FMI_DAILY_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0"
                       xmlns:BsWfs="http://xml.fmi.fi/schema/wfs/2.0">
  <wfs:member>
    <BsWfs:BsWfsElement>
      <BsWfs:Time>2100-01-01T12:00:00Z</BsWfs:Time>
      <BsWfs:ParameterName>Temperature</BsWfs:ParameterName>
      <BsWfs:ParameterValue>18.2</BsWfs:ParameterValue>
    </BsWfs:BsWfsElement>
  </wfs:member>
  <wfs:member>
    <BsWfs:BsWfsElement>
      <BsWfs:Time>2100-01-01T12:00:00Z</BsWfs:Time>
      <BsWfs:ParameterName>WeatherSymbol3</BsWfs:ParameterName>
      <BsWfs:ParameterValue>2</BsWfs:ParameterValue>
    </BsWfs:BsWfsElement>
  </wfs:member>
</wfs:FeatureCollection>"""

_FMI_EMPTY_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0"
                       xmlns:BsWfs="http://xml.fmi.fi/schema/wfs/2.0">
</wfs:FeatureCollection>"""


def _mock_fmi_hourly():
    """@brief Mock response carrying FMI hourly forecast XML."""
    return _mock_response(text=_FMI_HOURLY_XML)


def _mock_fmi_daily():
    """@brief Mock response carrying FMI daily forecast XML."""
    return _mock_response(text=_FMI_DAILY_XML)


def _mock_fmi_empty():
    """@brief Mock response carrying an empty FMI WFS collection."""
    return _mock_response(text=_FMI_EMPTY_XML)


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


def _mock_response(json_data=None, status_code=200, text=None):
    """@brief Build a mock requests.Response object.

    @param json_data   Python object returned by `.json()` (optional).
    @param status_code HTTP status code (default 200).
    @param text        String returned by `.text` (optional, for XML responses).
    @return MagicMock that mimics a `requests.Response`.
    """
    m = MagicMock()
    m.status_code = status_code
    if json_data is not None:
        m.json.return_value = json_data
    if text is not None:
        m.text = text
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

    def test_fmi_weather_symbol_mapping(self):
        """@brief get_fmi_weather_symbol() maps FMI WeatherSymbol3 codes to Unicode emojis."""
        self.assertEqual(get_fmi_weather_symbol(1), "\u2600")    # clear
        self.assertEqual(get_fmi_weather_symbol(2), "\u26c5")    # partly cloudy
        self.assertEqual(get_fmi_weather_symbol(3), "\u2601")    # cloudy
        self.assertEqual(get_fmi_weather_symbol(32), "\U0001f327")  # rain
        self.assertEqual(get_fmi_weather_symbol(61), "\u26c8")   # thunderstorm
        self.assertEqual(get_fmi_weather_symbol(52), "\u2744")   # snow
        self.assertEqual(get_fmi_weather_symbol(91), "\U0001f32b")  # fog
        self.assertEqual(get_fmi_weather_symbol(99), "")          # unknown code
        self.assertEqual(get_fmi_weather_symbol("nan"), "")       # unparseable string
        self.assertEqual(get_fmi_weather_symbol(None), "")        # None

    def test_wind_direction_as_text_fi_en(self):
        """@brief wind_direction_as_text() returns correct Finnish and English strings."""
        self.assertEqual(wind_direction_as_text(180, "fi"), "etelästä")
        self.assertEqual(wind_direction_as_text(180, "en"), "from S")
        self.assertEqual(wind_direction_as_text(None), "")

    def test_wind_direction_as_text_all_cardinal_directions_fi(self):
        """@brief wind_direction_as_text() maps every cardinal direction correctly in Finnish."""
        cases = [
            (45,  "koillisesta"),   # NE: 22.5–67.5
            (90,  "idästä"),        # E: 67.5–112.5
            (135, "kaakosta"),      # SE: 112.5–157.5
            (225, "lounaasta"),     # SW: 202.5–247.5
            (270, "lännestä"),      # W: 247.5–292.5
            (315, "luoteesta"),     # NW: 292.5–337.5
            (0,   "pohjoisesta"),   # N: 337.5–22.5
        ]
        for deg, expected in cases:
            with self.subTest(deg=deg):
                self.assertEqual(wind_direction_as_text(deg, "fi"), expected)

    def test_wind_direction_as_text_swedish(self):
        """@brief wind_direction_as_text() returns correct Swedish strings for sv locale."""
        self.assertEqual(wind_direction_as_text(180, "sv"), "från S")
        self.assertEqual(wind_direction_as_text(0,   "sv"), "från N")
        self.assertEqual(wind_direction_as_text(90,  "sv"), "från Ö")

    def test_wind_direction_as_text_wraps_degrees_above_360(self):
        """@brief wind_direction_as_text() normalises degrees > 360 by subtracting 360."""
        # 540 − 360 = 180 → S
        self.assertEqual(wind_direction_as_text(540, "fi"), "etelästä")

    def test_format_station_name_four_tokens(self):
        """@brief format_station_name() handles 4-token names by appending the extra token."""
        self.assertEqual(
            format_station_name("E18_Helsinki_Vantaa_Extra"),
            "Helsinki, Vantaa E18 Extra",
        )

    def test_format_station_name_two_tokens(self):
        """@brief format_station_name() handles 2-token names."""
        self.assertEqual(format_station_name("KEHÄ_Helsinki"), "Helsinki, KEHÄ")

    def test_format_station_name_single_token_unchanged(self):
        """@brief format_station_name() returns a single-token name unchanged."""
        self.assertEqual(format_station_name("JustOne"), "JustOne")


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

    def test_feels_like_returns_invalid_when_any_input_is_invalid(self):
        """@brief fmi_feels_like_temperature() returns INVALID_VALUE when any argument is INVALID_VALUE."""
        from weather.services.definitions import Constants
        iv = Constants.INVALID_VALUE
        self.assertEqual(fmi_feels_like_temperature(iv, 80.0, 10.0), iv)
        self.assertEqual(fmi_feels_like_temperature(5.0, iv, 10.0), iv)
        self.assertEqual(fmi_feels_like_temperature(5.0, 80.0, iv), iv)


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

    def test_sensor_parse_missing_key_returns_false(self):
        """@brief Sensor.parse() returns False when a required key is absent."""
        from weather.services.weather_station import Sensor
        self.assertFalse(Sensor().parse({}))
        self.assertFalse(Sensor().parse({"id": 1, "stationId": 2, "name": "X"}))

    def test_weather_station_visibility_100_to_999_m(self):
        """@brief visibility_str formats 100–999 m values rounded down to nearest 100 m."""
        ws = WeatherStation()
        payload = {**_STATION_DATA_PAYLOAD, "sensorValues": [
            {"id": 58, "stationId": 12345, "name": "NÄKYVYYS_M", "shortName": "Nak",
             "measuredTime": "2026-05-12T12:50:00Z", "value": 450, "unit": "m"},
        ]}
        ws.parse(payload)
        self.assertEqual(ws.visibility_str, "400 m")

    def test_weather_station_visibility_below_100_m(self):
        """@brief visibility_str formats < 100 m values rounded down to nearest 10 m."""
        ws = WeatherStation()
        payload = {**_STATION_DATA_PAYLOAD, "sensorValues": [
            {"id": 58, "stationId": 12345, "name": "NÄKYVYYS_M", "shortName": "Nak",
             "measuredTime": "2026-05-12T12:50:00Z", "value": 75, "unit": "m"},
        ]}
        ws.parse(payload)
        self.assertEqual(ws.visibility_str, "70 m")

    def test_weather_station_visibility_negative_returns_empty(self):
        """@brief visibility_str returns empty string when visibility is negative."""
        ws = WeatherStation()
        payload = {**_STATION_DATA_PAYLOAD, "sensorValues": [
            {"id": 58, "stationId": 12345, "name": "NÄKYVYYS_M", "shortName": "Nak",
             "measuredTime": "2026-05-12T12:50:00Z", "value": -1, "unit": "m"},
        ]}
        ws.parse(payload)
        self.assertEqual(ws.visibility_str, "")

    def test_present_weather_swedish(self):
        """@brief present_weather_localized('sv') returns Swedish-translated condition strings."""
        payload = {**_STATION_DATA_PAYLOAD, "sensorValues": [
            {"id": 22, "stationId": 12345, "name": "SADE", "shortName": "Sade",
             "measuredTime": "2026-05-12T12:50:00Z", "value": 0.0,
             "sensorValueDescriptionFi": "Pouta"},
        ]}
        ws = WeatherStation()
        ws.parse(payload)
        is_precip, text = ws.present_weather_localized("sv")
        self.assertFalse(is_precip)
        self.assertEqual(text, "Torrt")

        payload2 = {**_STATION_DATA_PAYLOAD, "sensorValues": [
            {"id": 22, "stationId": 12345, "name": "SADE", "shortName": "Sade",
             "measuredTime": "2026-05-12T12:50:00Z", "value": 2.0,
             "sensorValueDescriptionFi": "Kohtalainen"},
        ]}
        ws2 = WeatherStation()
        ws2.parse(payload2)
        is_precip2, text2 = ws2.present_weather_localized("sv")
        self.assertTrue(is_precip2)
        self.assertEqual(text2, "Måttligt regn")


# ── View / API endpoints ────────────────────────────────────
@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
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
    def test_api_station_data_with_fmi_forecast(self, mock_get):
        """@brief Station data response includes FMI-sourced forecast and current_symbol unconditionally."""
        mock_get.side_effect = [
            _mock_response(_STATION_LIST_PAYLOAD),
            _mock_response(_STATION_DATA_PAYLOAD),
            _mock_fmi_hourly(),
            _mock_fmi_daily(),
        ]
        r = self._get("/api/station/12345/")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["station_id"], 12345)
        self.assertEqual(data["station_name"], "Oulu, Ritaharju vt4")
        self.assertEqual(data["temperature_raw"], 10.7)
        # FMI forecast is always fetched — current_symbol from first hourly entry
        self.assertEqual(data["current_symbol"], "\u2600")  # WeatherSymbol3=1 → ☀
        self.assertEqual(len(data["forecast"]), 2)  # 1 hourly + 1 daily
        hourly = data["forecast"][0]
        self.assertEqual(hourly["time"], "21:00")
        self.assertEqual(hourly["date"], "2099-12-31")
        self.assertEqual(hourly["temperature"], "16 \u00b0C")  # round(15.5)
        self.assertEqual(hourly["symbol"], "\u2600")
        self.assertNotIn("daily", hourly)
        daily = data["forecast"][1]
        self.assertEqual(daily["time"], "")
        self.assertEqual(daily["date"], "2100-01-01")
        self.assertEqual(daily["temperature"], "18 \u00b0C")  # round(18.2)
        self.assertEqual(daily["symbol"], "\u26c5")  # WeatherSymbol3=2 → ⛅
        self.assertTrue(daily["daily"])

    @patch("weather.services.weather_service.requests.get")
    def test_api_station_data_fmi_error_degrades_gracefully(self, mock_get):
        """@brief Empty FMI response returns empty forecast alongside Digitraffic observations."""
        mock_get.side_effect = [
            _mock_response(_STATION_LIST_PAYLOAD),
            _mock_response(_STATION_DATA_PAYLOAD),
            _mock_fmi_empty(),
            _mock_fmi_empty(),
        ]
        r = self._get("/api/station/12345/")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["current_symbol"], "")
        self.assertEqual(data["forecast"], [])
        self.assertEqual(data["temperature_raw"], 10.7)  # Digitraffic data still present

    @patch("weather.services.weather_service.requests.get")
    def test_api_station_data_unknown_id(self, mock_get):
        """@brief Requesting a station id not present in the station list returns HTTP 502."""
        mock_get.return_value = _mock_response(_STATION_LIST_PAYLOAD)
        r = self._get("/api/station/77777/")
        self.assertEqual(r.status_code, 502)
        self.assertIn("error", r.json())

    @patch("weather.services.weather_service.requests.get")
    def test_api_nearest_station_returns_closest(self, mock_get):
        """@brief POST /api/nearest-station/ returns the station closest to the given coordinates."""
        mock_get.return_value = _mock_response(_STATION_LIST_PAYLOAD)
        # Station is at lat=65.0, lon=25.0 (from _STATION_LIST_PAYLOAD GeoJSON [lon, lat])
        r = self._post("/api/nearest-station/", data='{"lat": 65.0, "lon": 25.0}', content_type="application/json")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["id"], 12345)
        self.assertEqual(data["formatted_name"], "Oulu, Ritaharju vt4")

    def test_api_nearest_station_missing_params(self):
        """@brief POST /api/nearest-station/ without lat/lon returns HTTP 400."""
        r = self._post("/api/nearest-station/", data='{}', content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("error", r.json())

    def test_api_nearest_station_invalid_params(self):
        """@brief POST /api/nearest-station/ with non-numeric lat/lon returns HTTP 400."""
        r = self._post("/api/nearest-station/", data='{"lat": "abc", "lon": "xyz"}', content_type="application/json")
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

    @override_settings(WEATHER_RATE_LIMIT="2/m")
    @patch("weather.services.weather_service.requests.get")
    def test_api_station_data_rate_limited(self, mock_get):
        """@brief Third request from the same IP within the sliding window returns HTTP 429."""
        mock_get.side_effect = [
            _mock_response(_STATION_LIST_PAYLOAD),
            _mock_response(_STATION_DATA_PAYLOAD),
            _mock_fmi_hourly(),
            _mock_fmi_daily(),
        ]
        self._get("/api/station/12345/")  # 1st — ok (populates cache)
        self._get("/api/station/12345/")  # 2nd — ok (served from response cache)
        r = self._get("/api/station/12345/")  # 3rd — rate limited
        self.assertEqual(r.status_code, 429)
        self.assertIn("error", r.json())

    @patch("weather.services.weather_service.requests.get")
    def test_api_nearest_station_no_stations_returns_503(self, mock_get):
        """@brief POST /api/nearest-station/ returns 503 when the station list is empty."""
        mock_get.return_value = _mock_response({"features": []})
        r = self._post("/api/nearest-station/", data='{"lat": 60.0, "lon": 25.0}', content_type="application/json")
        self.assertEqual(r.status_code, 503)
        self.assertIn("error", r.json())

    def test_settings_save_non_dict_body_returns_400(self):
        """@brief POST /api/settings/save/ with a JSON array body returns HTTP 400."""
        r = self._post(
            "/api/settings/save/",
            data="[1, 2, 3]",
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("JSON object", r.json()["error"])

    def test_settings_save_invalid_language_returns_400(self):
        """@brief POST /api/settings/save/ with an unsupported language code returns HTTP 400."""
        r = self._post(
            "/api/settings/save/",
            data='{"language": "de"}',
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("language", r.json()["error"])

    def test_settings_save_invalid_show_camera_type_returns_400(self):
        """@brief POST /api/settings/save/ with show_camera as a non-boolean returns HTTP 400."""
        r = self._post(
            "/api/settings/save/",
            data='{"show_camera": "yes"}',
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("show_camera", r.json()["error"])

    def test_settings_save_invalid_follow_location_type_returns_400(self):
        """@brief POST /api/settings/save/ with follow_location as a non-boolean returns HTTP 400."""
        r = self._post(
            "/api/settings/save/",
            data='{"follow_location": 1}',
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("follow_location", r.json()["error"])

    def test_settings_save_invalid_station_id_returns_400(self):
        """@brief POST /api/settings/save/ with an invalid current_station_id returns HTTP 400."""
        for val in [0, -1, True, "abc"]:
            with self.subTest(val=val):
                r = self._post(
                    "/api/settings/save/",
                    data=json.dumps({"current_station_id": val}),
                    content_type="application/json",
                )
                self.assertEqual(r.status_code, 400)
                self.assertIn("current_station_id", r.json()["error"])

    def test_settings_save_station_name_too_long_returns_400(self):
        """@brief POST /api/settings/save/ with current_station_name > 200 chars returns HTTP 400."""
        r = self._post(
            "/api/settings/save/",
            data=json.dumps({"current_station_name": "x" * 201}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("current_station_name", r.json()["error"])


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class NextUpdateAtTests(SimpleTestCase):
    """@brief Unit tests for WeatherStation.next_update_at and seconds_until_next_update."""

    def _make_payload(self, ts: str) -> dict:
        return {**_STATION_DATA_PAYLOAD, "dataUpdatedTime": ts}

    def test_known_observation_time_returns_latest_plus_interval_plus_delay(self):
        """@brief next_update_at equals _latest_time + DEFAULT_DATA_REFRESH_INTERVAL_S + STATION_UPDATE_DELAY_S."""
        from weather.services.definitions import Constants
        obs = datetime.datetime(2026, 5, 12, 12, 50, 0, tzinfo=dt_timezone.utc)
        ws = WeatherStation()
        ws.parse(self._make_payload("2026-05-12T12:50:00Z"))
        expected = obs + datetime.timedelta(
            seconds=Constants.DEFAULT_DATA_REFRESH_INTERVAL_S + Constants.STATION_UPDATE_DELAY_S
        )
        self.assertEqual(ws.next_update_at, expected)

    def test_unknown_observation_time_returns_now_plus_default_interval(self):
        """@brief next_update_at falls back to now + DEFAULT_DATA_REFRESH_INTERVAL_S when observation time is unknown."""
        from django.utils import timezone as dj_tz

        from weather.services.definitions import Constants
        ws = WeatherStation()  # _latest_time stays at epoch (year=1970)
        before = dj_tz.now()
        result = ws.next_update_at
        after = dj_tz.now()
        self.assertGreaterEqual(result, before + datetime.timedelta(seconds=Constants.DEFAULT_DATA_REFRESH_INTERVAL_S))
        self.assertLessEqual(result, after + datetime.timedelta(seconds=Constants.DEFAULT_DATA_REFRESH_INTERVAL_S + 1))

    def test_seconds_until_next_update_recent_observation(self):
        """@brief seconds_until_next_update returns DEFAULT_DATA_REFRESH_INTERVAL_S + STATION_UPDATE_DELAY_S for a just-updated station."""
        from django.utils import timezone as dj_tz

        from weather.services.definitions import Constants
        now = dj_tz.now()
        ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        ws = WeatherStation()
        ws.parse(self._make_payload(ts))
        expected = Constants.DEFAULT_DATA_REFRESH_INTERVAL_S + Constants.STATION_UPDATE_DELAY_S
        result = ws.seconds_until_next_update
        self.assertGreaterEqual(result, expected - 2)
        self.assertLessEqual(result, expected + 2)

    def test_seconds_until_next_update_clamps_to_zero_when_overdue(self):
        """@brief seconds_until_next_update returns 0 when next_update_at is in the past."""
        ws = WeatherStation()
        ws._latest_time = datetime.datetime(2020, 1, 1, 0, 0, 0, tzinfo=dt_timezone.utc)
        self.assertEqual(ws.seconds_until_next_update, 0)

    def test_seconds_until_next_update_clamps_to_600_max(self):
        """@brief seconds_until_next_update is clamped to 600 even when DEFAULT_DATA_REFRESH_INTERVAL_S + STATION_UPDATE_DELAY_S would exceed it."""
        # Temporarily make the sum exceed 600 by using a future obs time far ahead
        from django.utils import timezone as dj_tz

        from weather.services.definitions import Constants
        future = dj_tz.now() + datetime.timedelta(seconds=700)
        ws = WeatherStation()
        ws._latest_time = future
        self.assertLessEqual(ws.seconds_until_next_update, 600)


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class StationDataCacheTests(SimpleTestCase):
    """@brief Tests for per-station response caching in api_station_data."""

    def setUp(self):
        cache.clear()
        self.client = Client(enforce_csrf_checks=False)
        self._get = lambda path, **kw: self.client.get(path, secure=True, **kw)

    @patch("weather.services.weather_service.requests.get")
    def test_cached_response_served_without_second_digitraffic_request(self, mock_get):
        """@brief Second request within next_update_at window is served from cache; no network calls made again."""
        mock_get.side_effect = [
            _mock_response(_STATION_LIST_PAYLOAD),
            _mock_response(_STATION_DATA_PAYLOAD),
            _mock_fmi_hourly(),
            _mock_fmi_daily(),
        ]
        self._get("/api/station/12345/")
        # Cache is now populated. A second request should not call mock_get again.
        self._get("/api/station/12345/")
        # mock_get was called exactly 4 times (station list + station data + 2x FMI), not 8.
        self.assertEqual(mock_get.call_count, 4)

    @patch("weather.services.weather_service.requests.get")
    def test_cache_bypassed_with_refresh_param(self, mock_get):
        """@brief ?refresh=1 bypasses the cache and fetches fresh data from Digitraffic and FMI."""
        mock_get.side_effect = [
            _mock_response(_STATION_LIST_PAYLOAD),
            _mock_response(_STATION_DATA_PAYLOAD),
            _mock_fmi_hourly(),
            _mock_fmi_daily(),
        ]
        self._get("/api/station/12345/")          # populate cache (4 calls)
        mock_get.side_effect = [
            _mock_response(_STATION_DATA_PAYLOAD),
            _mock_fmi_hourly(),
            _mock_fmi_daily(),
        ]
        r = self._get("/api/station/12345/?refresh=1")  # station list cached; re-fetches data + FMI
        self.assertEqual(r.status_code, 200)
        self.assertEqual(mock_get.call_count, 7)

    @patch("weather.services.weather_service.requests.get")
    def test_next_update_at_not_in_json_response(self, mock_get):
        """@brief The internal _next_update_at field is never exposed in the API response."""
        mock_get.side_effect = [
            _mock_response(_STATION_LIST_PAYLOAD),
            _mock_response(_STATION_DATA_PAYLOAD),
            _mock_fmi_hourly(),
            _mock_fmi_daily(),
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
            _mock_fmi_hourly(),
            _mock_fmi_daily(),
        ]
        self._get("/api/station/12345/")           # populate cache
        mock_get.side_effect = []                  # no further calls allowed
        r = self._get("/api/station/12345/")       # served from cache
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_next_update_at", r.json())

    @patch("weather.services.weather_service.requests.get")
    def test_different_language_gets_own_cache_entry(self, mock_get):
        """@brief Switching language triggers a fresh fetch; cache keys are language-scoped."""
        # First request in Finnish (default) — populates station_data:12345:fi
        mock_get.side_effect = [
            _mock_response(_STATION_LIST_PAYLOAD),
            _mock_response(_STATION_DATA_PAYLOAD),
            _mock_fmi_hourly(),
            _mock_fmi_daily(),
        ]
        self._get("/api/station/12345/")
        fi_call_count = mock_get.call_count  # 4

        # Second request in English — different cache key, must hit the network again
        mock_get.side_effect = [
            _mock_response(_STATION_DATA_PAYLOAD),
            _mock_fmi_hourly(),
            _mock_fmi_daily(),
        ]
        with patch("weather.views._get_settings", return_value={"language": "en"}):
            r = self._get("/api/station/12345/")
        self.assertEqual(r.status_code, 200)
        # 3 additional calls for English (station list already cached, data+2xFMI re-fetched)
        self.assertEqual(mock_get.call_count, fi_call_count + 3)

        # Third request, still English — must be served from cache (no extra calls)
        mock_get.side_effect = []
        with patch("weather.views._get_settings", return_value={"language": "en"}):
            r2 = self._get("/api/station/12345/")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(mock_get.call_count, fi_call_count + 3)


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


# ── Station info edge cases ─────────────────────────────────
class StationInfoTests(SimpleTestCase):
    """@brief Tests for WeatherStationInfo and WeatherStationList edge cases."""

    def test_station_info_parse_malformed_returns_false(self):
        """@brief WeatherStationInfo.parse() returns False when required fields are missing."""
        from weather.services.station_info import WeatherStationInfo
        self.assertFalse(WeatherStationInfo().parse({}))
        self.assertFalse(WeatherStationInfo().parse({"geometry": {}, "id": 1, "properties": {}}))

    def test_station_list_find_by_name(self):
        """@brief WeatherStationList.find_by_name() returns a station by formatted name or None."""
        sl = WeatherStationList()
        sl.parse(_STATION_LIST_PAYLOAD["features"])
        found = sl.find_by_name("Oulu, Ritaharju vt4")
        self.assertIsNotNone(found)
        self.assertEqual(found.id, 12345)
        self.assertIsNone(sl.find_by_name("Does Not Exist"))


# ── FmiXmlParser edge cases ─────────────────────────────────
class FmiXmlParserTests(SimpleTestCase):
    """@brief Tests for FmiXmlParser boundary conditions."""

    def test_parse_empty_string_returns_empty_dict(self):
        """@brief FmiXmlParser.parse() returns {} when xml_text is empty."""
        from weather.services.weather_service import FmiXmlParser
        self.assertEqual(FmiXmlParser.parse(""), {})

    def test_parse_invalid_xml_returns_empty_dict(self):
        """@brief FmiXmlParser.parse() returns {} on malformed XML input."""
        from weather.services.weather_service import FmiXmlParser
        self.assertEqual(FmiXmlParser.parse("<<<not valid xml>>>"), {})


# ── _parse_timestamp edge cases ──────────────────────────────
class ParseTimestampTests(SimpleTestCase):
    """@brief Tests for weather_station._parse_timestamp fallback behaviour."""

    def test_invalid_timestamp_returns_epoch(self):
        """@brief _parse_timestamp() falls back to epoch datetime on unparseable input."""
        from weather.services.weather_station import _parse_timestamp
        result = _parse_timestamp("xXxNOT_A_DATE!@#")
        self.assertEqual(result.year, 1970)


# ── Settings validation: show_history and history_hours ──────
@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class SettingsHistoryValidationTests(SimpleTestCase):
    """@brief Tests for _validate_settings_body() fields added with the history feature."""

    def setUp(self):
        cache.clear()
        self.client = Client(enforce_csrf_checks=False)
        self._post = lambda path, **kw: self.client.post(path, secure=True, **kw)

    def test_settings_save_show_history_non_bool_returns_400(self):
        """@brief POST /api/settings/save/ with show_history as a non-boolean returns HTTP 400."""
        r = self._post(
            "/api/settings/save/",
            data='{"show_history": "yes"}',
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("show_history", r.json()["error"])

    def test_settings_save_history_hours_wrong_type_returns_400(self):
        """@brief POST /api/settings/save/ with history_hours as a float/string returns HTTP 400."""
        for val in ["12", 12.5, True]:
            with self.subTest(val=val):
                r = self._post(
                    "/api/settings/save/",
                    data=json.dumps({"history_hours": val}),
                    content_type="application/json",
                )
                self.assertEqual(r.status_code, 400)
                self.assertIn("history_hours", r.json()["error"])

    def test_settings_save_history_hours_out_of_range_returns_400(self):
        """@brief POST /api/settings/save/ with history_hours outside 1–24 returns HTTP 400."""
        for val in [0, 25, -1]:
            with self.subTest(val=val):
                r = self._post(
                    "/api/settings/save/",
                    data=json.dumps({"history_hours": val}),
                    content_type="application/json",
                )
                self.assertEqual(r.status_code, 400)
                self.assertIn("history_hours", r.json()["error"])

    def test_settings_save_show_history_and_history_hours_valid(self):
        """@brief POST /api/settings/save/ with valid show_history and history_hours returns HTTP 200."""
        r = self._post(
            "/api/settings/save/",
            data='{"show_history": false, "history_hours": 6}',
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"ok": True})

        r = self.client.get("/api/settings/", secure=True)
        data = r.json()
        self.assertFalse(data["show_history"])
        self.assertEqual(data["history_hours"], 6)


# ── WeatherService.get_station_history() ─────────────────────
class StationHistoryServiceTests(SimpleTestCase):
    """@brief Unit tests for WeatherService.get_station_history()."""

    def _make_history_payload(self, temp_value=None, precip_value=None):
        """Build a history payload with optional temperature and/or precipitation values.

        Uses a timestamp 30 minutes ago so it falls within any reasonable window.
        """
        now = datetime.datetime.now(dt_timezone.utc)
        ts = (now - datetime.timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        values = []
        if temp_value is not None:
            values.append({"id": 1, "measuredTime": ts, "value": temp_value})
        if precip_value is not None:
            values.append({"id": 23, "measuredTime": ts, "value": precip_value})
        return {"values": values}

    @patch("weather.services.weather_service.requests.get")
    def test_get_station_history_returns_correct_structure(self, mock_get):
        """@brief get_station_history() always returns temp_series, precip_series, and has_precipitation."""
        mock_get.return_value = _mock_response(self._make_history_payload(temp_value=10.5))
        svc = WeatherService()
        result = svc.get_station_history(12345, hours=1)
        self.assertIn("temp_series", result)
        self.assertIn("precip_series", result)
        self.assertIn("has_precipitation", result)
        self.assertIsInstance(result["temp_series"], list)
        self.assertIsInstance(result["precip_series"], list)
        self.assertIsInstance(result["has_precipitation"], bool)

    @patch("weather.services.weather_service.requests.get")
    def test_get_station_history_temp_series_entries_have_correct_shape(self, mock_get):
        """@brief Each temp_series entry has 'time' (ISO 8601) and 'temperature' (float or None)."""
        mock_get.return_value = _mock_response(self._make_history_payload(temp_value=12.3))
        svc = WeatherService()
        result = svc.get_station_history(12345, hours=1)
        self.assertTrue(len(result["temp_series"]) > 0)
        for entry in result["temp_series"]:
            self.assertIn("time", entry)
            self.assertIn("temperature", entry)

    @patch("weather.services.weather_service.requests.get")
    def test_get_station_history_valid_temp_value_appears_in_series(self, mock_get):
        """@brief A valid temperature reading within the window appears as a non-None bucket.

        Uses hours=24 so the 24-hour series window safely covers a measurement
        taken 30 minutes ago. With hours=1 the series starts at ceil(now-1h) to
        the next full hour boundary, which can exclude a reading at now-30min
        whose bucket falls before that boundary.
        """
        mock_get.return_value = _mock_response(self._make_history_payload(temp_value=15.3))
        svc = WeatherService()
        result = svc.get_station_history(12345, hours=24)
        non_null_temps = [e["temperature"] for e in result["temp_series"] if e["temperature"] is not None]
        self.assertEqual(len(non_null_temps), 1)
        self.assertEqual(non_null_temps[0], 15.3)

    @patch("weather.services.weather_service.requests.get")
    def test_get_station_history_has_precipitation_true_when_precip_sensor_present(self, mock_get):
        """@brief has_precipitation is True when the station reports any precipitation sensor value."""
        mock_get.return_value = _mock_response(self._make_history_payload(temp_value=5.0, precip_value=0.5))
        svc = WeatherService()
        result = svc.get_station_history(12345, hours=1)
        self.assertTrue(result["has_precipitation"])

    @patch("weather.services.weather_service.requests.get")
    def test_get_station_history_has_precipitation_false_when_no_precip_sensor(self, mock_get):
        """@brief has_precipitation is False when only temperature sensor data is present."""
        mock_get.return_value = _mock_response(self._make_history_payload(temp_value=5.0))
        svc = WeatherService()
        result = svc.get_station_history(12345, hours=1)
        self.assertFalse(result["has_precipitation"])

    @patch("weather.services.weather_service.requests.get")
    def test_get_station_history_http_error_returns_empty_series(self, mock_get):
        """@brief get_station_history() returns empty series and sets has_error on upstream failure."""
        mock_get.return_value = _mock_http_error_response(503)
        svc = WeatherService()
        result = svc.get_station_history(12345, hours=1)
        self.assertEqual(result, {"temp_series": [], "precip_series": [], "has_precipitation": False})
        self.assertTrue(svc.has_error)

    @patch("weather.services.weather_service.requests.get")
    def test_get_station_history_filters_invalid_sensor_values(self, mock_get):
        """@brief Sensor readings at or below INVALID_VALUE (-999) are excluded from all buckets."""
        from weather.services.definitions import Constants
        now = datetime.datetime.now(dt_timezone.utc)
        ts = (now - datetime.timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        payload = {"values": [
            {"id": 1, "measuredTime": ts, "value": Constants.INVALID_VALUE},
            {"id": 1, "measuredTime": ts, "value": Constants.INVALID_VALUE - 1},
        ]}
        mock_get.return_value = _mock_response(payload)
        svc = WeatherService()
        result = svc.get_station_history(12345, hours=1)
        # No valid readings → every bucket should be None
        for entry in result["temp_series"]:
            self.assertIsNone(entry["temperature"])

    @patch("weather.services.weather_service.requests.get")
    def test_get_station_history_empty_values_list_returns_empty_series(self, mock_get):
        """@brief An empty values list from the API produces series with all-None buckets."""
        mock_get.return_value = _mock_response({"values": []})
        svc = WeatherService()
        result = svc.get_station_history(12345, hours=1)
        self.assertFalse(svc.has_error)
        self.assertFalse(result["has_precipitation"])
        for entry in result["temp_series"]:
            self.assertIsNone(entry["temperature"])


# ── api_station_history view ──────────────────────────────────
@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class StationHistoryViewTests(SimpleTestCase):
    """@brief Integration tests for the GET /api/station-history/<id>/ endpoint."""

    def setUp(self):
        cache.clear()
        self.client = Client(enforce_csrf_checks=False)
        self._get = lambda path, **kw: self.client.get(path, secure=True, **kw)

    @patch("weather.views.WeatherService")
    def test_api_station_history_returns_correct_keys(self, MockWeatherService):
        """@brief GET /api/station-history/<id>/ returns temp_series, precip_series, has_precipitation."""
        mock_svc = MockWeatherService.return_value
        mock_svc.has_error = False
        mock_svc.get_station_history.return_value = {
            "temp_series": [{"time": "2026-05-12T12:00:00Z", "temperature": 10.5}],
            "precip_series": [{"time": "2026-05-12T12:00:00Z", "precipitation": None}],
            "has_precipitation": False,
        }
        r = self._get("/api/station-history/12345/")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("temp_series", data)
        self.assertIn("precip_series", data)
        self.assertIn("has_precipitation", data)

    @patch("weather.views.WeatherService")
    def test_api_station_history_upstream_error_returns_502(self, MockWeatherService):
        """@brief GET /api/station-history/<id>/ returns HTTP 502 when the upstream service fails."""
        mock_svc = MockWeatherService.return_value
        mock_svc.has_error = True
        mock_svc.error_message = "Upstream service error (HTTP 503)"
        mock_svc.get_station_history.return_value = {
            "temp_series": [], "precip_series": [], "has_precipitation": False,
        }
        r = self._get("/api/station-history/12345/")
        self.assertEqual(r.status_code, 502)
        self.assertIn("error", r.json())

    @patch("weather.views.WeatherService")
    def test_api_station_history_cached_response_served_without_second_service_call(self, MockWeatherService):
        """@brief Second request within the 5-minute TTL is served from cache; service not called again."""
        mock_svc = MockWeatherService.return_value
        mock_svc.has_error = False
        mock_svc.get_station_history.return_value = {
            "temp_series": [], "precip_series": [], "has_precipitation": False,
        }
        self._get("/api/station-history/12345/")
        self._get("/api/station-history/12345/")
        self.assertEqual(mock_svc.get_station_history.call_count, 1)

    @override_settings(WEATHER_RATE_LIMIT="2/m")
    @patch("weather.views.WeatherService")
    def test_api_station_history_rate_limited(self, MockWeatherService):
        """@brief Third request from the same IP within the rate-limit window returns HTTP 429."""
        mock_svc = MockWeatherService.return_value
        mock_svc.has_error = False
        mock_svc.get_station_history.return_value = {
            "temp_series": [], "precip_series": [], "has_precipitation": False,
        }
        self._get("/api/station-history/12345/")  # 1st — ok
        self._get("/api/station-history/12345/")  # 2nd — ok (from cache, but rate counter increments)
        r = self._get("/api/station-history/12345/")  # 3rd — rate limited
        self.assertEqual(r.status_code, 429)
        self.assertIn("error", r.json())

    @patch("weather.views.WeatherService")
    def test_api_station_history_uses_history_hours_from_session(self, MockWeatherService):
        """@brief get_station_history() is called with the history_hours value from user session."""
        mock_svc = MockWeatherService.return_value
        mock_svc.has_error = False
        mock_svc.get_station_history.return_value = {
            "temp_series": [], "precip_series": [], "has_precipitation": False,
        }
        with patch("weather.views._get_settings", return_value={**{"history_hours": 3}}):
            self._get("/api/station-history/12345/")
        mock_svc.get_station_history.assert_called_once_with(12345, 3)


# ── PermissionsPolicyMiddleware ───────────────────────────────
class MiddlewareTests(SimpleTestCase):
    """@brief Tests for PermissionsPolicyMiddleware header injection."""

    def setUp(self):
        self.client = Client(enforce_csrf_checks=False)

    def test_permissions_policy_header_present_on_index(self):
        """@brief Every response includes a Permissions-Policy header."""
        r = self.client.get("/", secure=True)
        self.assertIn("Permissions-Policy", r)

    def test_permissions_policy_header_allows_geolocation_self(self):
        """@brief Permissions-Policy header grants geolocation to self (required for nearest-station feature)."""
        r = self.client.get("/", secure=True)
        self.assertIn("geolocation=(self)", r["Permissions-Policy"])

    def test_permissions_policy_header_disables_camera_and_microphone(self):
        """@brief Permissions-Policy header explicitly disables camera and microphone."""
        r = self.client.get("/", secure=True)
        policy = r["Permissions-Policy"]
        self.assertIn("camera=()", policy)
        self.assertIn("microphone=()", policy)
