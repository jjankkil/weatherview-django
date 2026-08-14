*** Settings ***
Documentation    Settings panel opens, controls reflect defaults, changes are saved.
...              Real markup (weather/templates/weather/index.html): #settings-modal,
...              #settings-close, #show-history-toggle, #history-hours-input,
...              #settings-save. #settings-btn opens the modal (see tests/e2e/test_ui.py
...              test_settings_modal_has_show_history_and_history_hours_controls).
Resource         ../resources/browser.resource
Suite Setup      Run Keywords    Start Django Server With Fixtures    AND    Open Weather App
Suite Teardown   Run Keywords    Close Browser    AND    Stop Django Server    AND    Stop Fixture Server
Test Setup       Accept Cookie Banner
Test Tags        e2e

*** Test Cases ***
Settings Button Opens Panel With Defaults
    Get Text    id=station-select    contains    Helsinki
    Click    id=settings-btn
    Get Element States    id=settings-modal    contains    visible
    Get Checkbox State    id=show-history-toggle    ==    checked
    Get Attribute    id=history-hours-input    value    ==    12

Close Button Dismisses Panel
    Get Text    id=station-select    contains    Helsinki
    Click    id=settings-btn
    Get Element States    id=settings-modal    contains    visible
    Click    id=settings-close
    Get Element States    id=settings-modal    contains    hidden

Disabling Show History Hides Trend Section
    [Documentation]    Mirrors tests/e2e/test_ui.py test_disabling_show_history_hides_trend_section.
    Get Text    id=station-select    contains    Helsinki
    Wait For Elements State    id=trend-section    visible
    Click    id=settings-btn
    Uncheck Checkbox    id=show-history-toggle
    Click    id=settings-save
    Wait For Elements State    id=trend-section    hidden
