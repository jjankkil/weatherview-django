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
    [Documentation]    Waits for the initial fallback request before selecting fixture station 1002.
    Get Text    id=station-select    contains    Tampere
    Wait For Condition    Text    id=temp-value    ==    -2.5 °C    timeout=10s
    Select Options By    id=station-select    value    1002
    Wait For Condition    Text    id=temp-value    ==    5.0 °C    timeout=10s
    Wait For Condition    Text    id=wind-value    ==    2.0 m/s    timeout=10s
    Get Element States    id=weather-card    contains    visible
