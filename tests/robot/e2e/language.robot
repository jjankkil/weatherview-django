*** Settings ***
Documentation    Language-switching tests: UI text updates when the language changes.
Resource         ../resources/browser.resource
Suite Setup      Run Keywords    Start Django Server With Fixtures    AND    Open Weather App
Suite Teardown   Run Keywords    Close Browser    AND    Stop Django Server    AND    Stop Fixture Server
Test Setup       Accept Cookie Banner
Test Tags        e2e

*** Test Cases ***
Language Defaults To Finnish
    Get Text    id=app-title    ==    Tiesää

Switch To English Updates Title
    [Documentation]    Wait for the station dropdown to populate first — otherwise the
    ...                click can land before app.js has attached its event listeners
    ...                (mirrors the wait in tests/e2e/test_ui.py test_language_switch_updates_all_labels).
    Get Text    id=station-select    contains    Helsinki
    Click    id=lang-btn
    Wait For Elements State    id=lang-list    visible
    Click    css=.lang-option[data-value="en"]
    Get Text    id=app-title    ==    Road Weather

Switch To Swedish Updates Title
    Get Text    id=station-select    contains    Helsinki
    Click    id=lang-btn
    Click    css=.lang-option[data-value="sv"]
    Get Text    id=app-title    ==    Vägväder

Language Setting Persists After Page Reload
    Get Text    id=station-select    contains    Helsinki
    Click    id=lang-btn
    Click    css=.lang-option[data-value="en"]
    Get Text    id=app-title    ==    Road Weather
    Reload
    Get Text    id=app-title    ==    Road Weather
