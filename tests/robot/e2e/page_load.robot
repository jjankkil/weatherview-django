*** Settings ***
Documentation    Smoke tests: page loads correctly and core elements are present.
Resource         ../resources/browser.resource
Suite Setup      Run Keywords    Start Django Server With Fixtures    AND    Open Weather App
Suite Teardown   Run Keywords    Close Browser    AND    Stop Django Server    AND    Stop Fixture Server
Test Setup       Accept Cookie Banner
Test Tags        e2e    smoke

*** Test Cases ***
Page Title Is Correct
    Get Title    ==    Tiesää – Road Weather

App Header Is Visible
    Get Element    id=app-title
    Get Text    id=app-title    ==    Tiesää

Station Selector Is Present And Populated
    Get Element    id=station-select
    Get Element Count    id=station-select    ==    1
    Get Text    id=station-select    contains    Helsinki

Language Dropdown Is Present
    Get Element    id=lang-btn

Settings Button Is Present
    Get Element    id=settings-btn
