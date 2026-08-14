*** Settings ***
Documentation    Selecting a station from the dropdown renders its weather data.
...              Mirrors tests/e2e/test_ui.py test_selecting_station_renders_weather_data,
...              using the fixture server's station 1002 (Tampere) whose temperature is
...              "5.0 °C" (see tests/robot/fixtures/fixture_server.py _STATION_SENSORS).
Resource         ../resources/browser.resource
Suite Setup      Run Keywords    Start Django Server With Fixtures    AND    Open Weather App
Suite Teardown   Run Keywords    Close Browser    AND    Stop Django Server    AND    Stop Fixture Server
Test Setup       Accept Cookie Banner
Test Tags        e2e

*** Test Cases ***
Both Fixture Stations Appear In The Dropdown
    Get Text    id=station-select    contains    Helsinki
    Get Text    id=station-select    contains    Tampere

Selecting A Station Renders Its Weather Data
    [Documentation]    Waits for the geolocation-fallback fetch of the initial station
    ...                (1001) to settle before switching to 1002 — app.js has no guard
    ...                against out-of-order fetch responses, so switching immediately
    ...                can let the still-in-flight 1001 response overwrite 1002's data.
    Get Text    id=station-select    contains    Tampere
    Get Text    id=temp-value    ==    -2.5 °C
    Select Options By    id=station-select    value    1002
    Get Text    id=temp-value    ==    5.0 °C
    Get Text    id=wind-value    ==    2.0 m/s
    Get Element States    id=weather-card    contains    visible
