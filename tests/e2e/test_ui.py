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

_HISTORY_DATA = {
    "temp_series": [
        {"time": "2026-06-28T10:00:00Z", "temperature": 12.5},
        {"time": "2026-06-28T10:10:00Z", "temperature": 13.0},
        {"time": "2026-06-28T10:20:00Z", "temperature": 13.5},
    ],
    "precip_series": [
        {"time": "2026-06-28T10:00:00Z", "precipitation": None},
    ],
    "has_precipitation": False,
}

_HISTORY_DATA_WITH_RAIN_12H = {
    "temp_series": [
        {"time": "2026-06-28T10:00:00Z", "temperature": 12.5},
    ],
    # 12 hourly buckets (shown window) summing to 3.5 mm
    "precip_series": [
        {"time": f"2026-06-28T{h:02d}:00:00Z", "precipitation": v}
        for h, v in zip(range(0, 12), [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, None, 0, 0, 0, 0])
    ],
    "has_precipitation": True,
    "rain_sum_24h": 5.0,
}

_HISTORY_DATA_WITH_RAIN_24H = {
    "temp_series": [
        {"time": "2026-06-28T10:00:00Z", "temperature": 12.5},
    ],
    # 24 hourly buckets (shown window == full 24h window)
    "precip_series": [
        {"time": f"2026-06-28T{h:02d}:00:00Z", "precipitation": 0.2}
        for h in range(24)
    ],
    "has_precipitation": True,
    "rain_sum_24h": 4.8,
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


def _mock_all_apis(page: Page, history_data=_HISTORY_DATA) -> None:
    """Register route mocks for all external endpoints including station history."""
    _mock_external_apis(page)
    page.route("**/api/station-history/**", lambda route: _fulfill_json(route, history_data))


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

    # #app-title is static HTML, so the assertion above passes before app.js has
    # attached its event listeners. Wait for a JS-populated element to guarantee
    # initEvents() has run before clicking JS-driven controls.
    expect(page.locator("#station-select")).to_contain_text("Helsinki / Pasila")

    # Open language dropdown and choose English
    page.locator("#lang-btn").click()
    expect(page.locator("#lang-list")).to_be_visible()
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


@pytest.mark.show_cookie_banner
def test_cookie_banner_shows_on_first_visit_and_dismisses(page: Page, base_url: str) -> None:
    """Cookie consent banner is visible on first visit and hidden after clicking Accept."""
    _mock_external_apis(page)
    page.goto(base_url)

    banner = page.locator("#cookie-banner")
    ok_btn = page.locator("#cookie-banner-ok")

    # Banner must be visible on first visit (no prior consent in localStorage)
    expect(banner).to_be_visible()
    expect(ok_btn).to_be_visible()

    # Clicking Accept hides the banner
    ok_btn.click()
    expect(banner).to_be_hidden()

    # Reloading must not show the banner again (localStorage flag persists)
    _mock_external_apis(page)
    page.reload()
    expect(banner).to_be_hidden()


def test_trend_section_appears_when_history_data_is_available(page: Page, base_url: str) -> None:
    """Trend section becomes visible after selecting a station and receiving history data."""
    _mock_all_apis(page)
    page.goto(base_url)

    select = page.locator("#station-select")
    # Geolocation fallback auto-selects a station on load, which pushes it to the
    # MRU list; populateStations then renders it in both the "Recent" and "All
    # stations" optgroups, so a value-based option locator is non-unique. Wait for
    # the station name instead (matches test_settings_language_persists_across_reload).
    expect(select).to_contain_text("Helsinki / Pasila")
    select.select_option(value="1001")

    # Weather card renders first, then history arrives asynchronously
    expect(page.locator("#weather-card")).to_be_visible()
    expect(page.locator("#trend-section")).to_be_visible()


def test_settings_modal_has_show_history_and_history_hours_controls(page: Page, base_url: str) -> None:
    """Settings modal contains the show_history toggle and history_hours input."""
    _mock_external_apis(page)
    page.goto(base_url)

    # Wait for stations to load — confirms JS event listeners are attached
    expect(page.locator("#station-select")).to_contain_text("Helsinki / Pasila")

    page.locator("#settings-btn").click()
    expect(page.locator("#settings-modal")).to_be_visible()

    # New history controls must be present with correct defaults
    expect(page.locator("#show-history-toggle")).to_be_visible()
    expect(page.locator("#show-history-toggle")).to_be_checked()
    expect(page.locator("#history-hours-input")).to_be_visible()
    expect(page.locator("#history-hours-input")).to_have_value("12")


def test_disabling_show_history_hides_trend_section(page: Page, base_url: str) -> None:
    """Unchecking show_history in settings and saving removes the trend section."""
    _mock_all_apis(page)
    page.goto(base_url)

    # Select a station to trigger history fetch → trend section becomes visible.
    # Use to_contain_text (not a value-based option locator): geolocation fallback
    # auto-selects a station and populateStations renders it in both the "Recent"
    # and "All stations" optgroups, making option[value='1001'] non-unique.
    select = page.locator("#station-select")
    expect(select).to_contain_text("Helsinki / Pasila")
    select.select_option(value="1001")
    expect(page.locator("#trend-section")).to_be_visible()

    # Open settings, uncheck show_history, save
    page.locator("#settings-btn").click()
    expect(page.locator("#settings-modal")).to_be_visible()
    page.locator("#show-history-toggle").uncheck()
    page.locator("#settings-save").click()

    # Trend section must now be hidden
    expect(page.locator("#trend-section")).to_be_hidden()


def test_rain_summary_shows_both_sums_when_history_shorter_than_24h(page: Page, base_url: str) -> None:
    """Both rain sum numbers render when the shown history window is under 24h."""
    _mock_all_apis(page, history_data=_HISTORY_DATA_WITH_RAIN_12H)
    page.goto(base_url)

    select = page.locator("#station-select")
    expect(select).to_contain_text("Helsinki / Pasila")
    select.select_option(value="1001")

    expect(page.locator("#trend-summary")).to_be_visible()
    expect(page.locator("#trend-summary-24h")).to_be_visible()
    expect(page.locator("#trend-summary-24h-value")).to_have_text("5.0 mm")
    expect(page.locator("#trend-summary-total")).to_be_visible()
    expect(page.locator("#trend-summary-total-value")).to_have_text("3.5 mm")


def test_rain_summary_shows_only_24h_sum_when_history_is_24h(page: Page, base_url: str) -> None:
    """Only the 24h rain sum renders when the shown history window is the full 24h."""
    _mock_all_apis(page, history_data=_HISTORY_DATA_WITH_RAIN_24H)
    page.goto(base_url)

    # Wait for stations to load — confirms JS event listeners are attached
    expect(page.locator("#station-select")).to_contain_text("Helsinki / Pasila")

    # Set history length to 24h before selecting a station, so the initial
    # history fetch already reflects the 24h window.
    page.locator("#settings-btn").click()
    expect(page.locator("#settings-modal")).to_be_visible()
    page.locator("#history-hours-input").fill("24")
    page.locator("#settings-save").click()

    select = page.locator("#station-select")
    expect(select).to_contain_text("Helsinki / Pasila")
    select.select_option(value="1001")

    expect(page.locator("#trend-summary")).to_be_visible()
    expect(page.locator("#trend-summary-24h")).to_be_visible()
    expect(page.locator("#trend-summary-24h-value")).to_have_text("4.8 mm")
    expect(page.locator("#trend-summary-total")).to_be_hidden()
