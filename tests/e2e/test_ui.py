"""Playwright end-to-end tests for the weatherview-django frontend.

Each test registers Playwright route mocks for the external-data endpoints
(``/api/stations/`` and ``/api/station/<id>/``) so the suite runs without a
live Digitraffic/FMI connection or a Redis instance.

Settings endpoints (``/api/settings/`` and ``/api/settings/save/``) hit the
real Django server because they only use signed-cookie sessions — no cache.

Run with:
    pytest tests/e2e/           (uses pytest.ini testpaths)
    pytest tests/e2e/ --headed  (opens a visible browser window)
"""

import json

import pytest
from playwright.sync_api import Page, expect

# ── Mock API payloads ─────────────────────────────────────────────────────────

_STATIONS = {
    "stations": [
        {
            "id": 1001,
            "name": "HELSINKI / PASILA",
            "formatted_name": "Helsinki / Pasila",
            "lat": 60.198,
            "lon": 24.932,
        },
        {
            "id": 1002,
            "name": "TAMPERE / AIRANTEENTIE",
            "formatted_name": "Tampere / Airanteentie",
            "lat": 61.497,
            "lon": 23.763,
        },
    ]
}

_WEATHER_BASE = {
    "observation_time": "22.06.2026 12:00",
    "temperature": "-2.5 °C",
    "temperature_raw": -2.5,
    "feels_like": "-5 °C",
    "temperature_change": "",
    "wind_speed": "3.2 m/s",
    "wind_speed_raw": 3.2,
    "wind_max": "5.0 m/s",
    "wind_direction": "pohjoiseen",
    "humidity": "78 %",
    "dew_point": "-5.8 °C",
    "road_temperature": "-3.0 °C",
    "visibility": "",
    "present_weather_label": "",
    "present_weather": "",
    "present_weather_is_precipitation": False,
    "current_symbol": "☁️",
    "forecast": [],
    "seconds_until_next_update": 300,
}

_WEATHER_1001 = {**_WEATHER_BASE, "station_id": 1001, "station_name": "Helsinki / Pasila"}
_WEATHER_1002 = {
    **_WEATHER_BASE,
    "station_id": 1002,
    "station_name": "Tampere / Airanteentie",
    "temperature": "5.0 °C",
    "temperature_raw": 5.0,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fulfill_json(route, data):
    """Fulfill a Playwright route request with a JSON response."""
    route.fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps(data),
    )


def _mock_external_apis(page: Page) -> None:
    """Register route mocks for the endpoints that call external services.

    ``/api/settings/`` and ``/api/settings/save/`` are intentionally NOT mocked
    so real session-cookie persistence can be exercised.
    """
    page.route("**/api/stations/", lambda route: _fulfill_json(route, _STATIONS))

    def _station_handler(route):
        if "/api/station/1002/" in route.request.url:
            _fulfill_json(route, _WEATHER_1002)
        else:
            _fulfill_json(route, _WEATHER_1001)

    page.route("**/api/station/**", _station_handler)


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_page_loads_and_station_list_populates(page: Page, base_url: str) -> None:
    """Page renders and the station dropdown is populated from /api/stations/."""
    _mock_external_apis(page)
    page.goto(base_url)

    # Page title should be rendered
    expect(page).to_have_title("Tiesää – Road Weather")

    select = page.locator("#station-select")
    # Both station names must appear in the dropdown
    expect(select).to_contain_text("Helsinki / Pasila")
    expect(select).to_contain_text("Tampere / Airanteentie")


def test_selecting_station_renders_weather_data(page: Page, base_url: str) -> None:
    """Selecting a station from the dropdown renders its weather data card."""
    _mock_external_apis(page)
    page.goto(base_url)

    # Wait until both stations are loaded
    select = page.locator("#station-select")
    expect(select.locator("option[value='1002']")).to_be_attached()

    # Select station 1002 — its mock response has temperature "5.0 °C"
    select.select_option(value="1002")

    expect(page.locator("#temp-value")).to_have_text("5.0 °C")
    expect(page.locator("#wind-value")).to_have_text("3.2 m/s")
    # Weather card must be visible (not hidden)
    expect(page.locator("#weather-card")).to_be_visible()


def test_language_switch_updates_all_labels(page: Page, base_url: str) -> None:
    """Switching to English updates the app title and static UI labels."""
    _mock_external_apis(page)
    page.goto(base_url)

    # Finnish is the default — verify before switching
    expect(page.locator("#app-title")).to_have_text("Tiesää")

    # Open language dropdown and choose English
    page.locator("#lang-btn").click()
    page.locator(".lang-option[data-value='en']").click()

    # App title and a data label should now be in English
    expect(page.locator("#app-title")).to_have_text("Road Weather")
    expect(page.locator("#temp-label")).to_have_text("Temperature:")
    expect(page.locator("#wind-label")).to_have_text("Wind speed (avg):")


def test_settings_language_persists_across_reload(page: Page, base_url: str) -> None:
    """Language saved via /api/settings/save/ is restored from session on reload."""
    _mock_external_apis(page)
    page.goto(base_url)

    # Confirm Finnish default
    expect(page.locator("#app-title")).to_have_text("Tiesää")

    # Select a specific station so current_station_id is saved to the session
    select = page.locator("#station-select")
    # After geolocation fallback, populateStations may create MRU optgroups which
    # duplicate entries — wait for the station name rather than a strict option locator
    expect(select).to_contain_text("Helsinki / Pasila")
    select.select_option(value="1001")
    expect(page.locator("#temp-value")).to_have_text("-2.5 °C")

    # Switch to English — this POSTs to /api/settings/save/ (real Django session)
    page.locator("#lang-btn").click()
    page.locator(".lang-option[data-value='en']").click()
    expect(page.locator("#app-title")).to_have_text("Road Weather")

    # Reload: route mocks persist; session cookie is replayed automatically
    page.reload()

    # Language should still be English after reload
    expect(page.locator("#app-title")).to_have_text("Road Weather")
