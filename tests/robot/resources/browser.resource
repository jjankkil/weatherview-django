*** Settings ***
Documentation    Browser startup helpers for the E2E suites.
Library          Browser
Resource         common.resource

*** Variables ***
${BROWSER}     chromium
${HEADLESS}    true

*** Keywords ***
Open Weather App
    [Documentation]    Opens a new browser page pointing at the app's root URL.
    ...    Geolocation permission is left ungranted, so the app's own fallback
    ...    (weather/static/weather/js/geo.js selectNearestByGeolocation) selects
    ...    the alphabetically-first station deterministically.
    New Browser    browser=${BROWSER}    headless=${HEADLESS}
    New Context
    New Page    ${BASE_URL}

Accept Cookie Banner
    [Documentation]    Pre-sets the consent flag the same way tests/e2e/conftest.py does,
    ...    then reloads so the app boots with the banner already dismissed.
    LocalStorage Set Item    cookie_consent_v1    1
    Reload
