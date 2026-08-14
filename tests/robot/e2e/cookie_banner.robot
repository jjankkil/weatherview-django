*** Settings ***
Documentation    Cookie consent banner is shown on first visit and hidden after acceptance.
...              Real markup (weather/templates/weather/index.html): #cookie-banner /
...              #cookie-banner-ok. Consent is a localStorage flag "cookie_consent_v1"
...              (see weather/static/weather/js/app.js and tests/e2e/conftest.py).
Resource         ../resources/browser.resource
Suite Setup      Start Django Server With Fixtures
Suite Teardown   Run Keywords    Stop Django Server    AND    Stop Fixture Server
Test Setup       New Browser    browser=${BROWSER}    headless=${HEADLESS}
Test Teardown    Close Browser
Test Tags        e2e

*** Test Cases ***
Banner Is Visible On First Visit
    New Context
    New Page    ${BASE_URL}
    Get Element States    id=cookie-banner    contains    visible

Banner Disappears After Acceptance
    New Context
    New Page    ${BASE_URL}
    Get Element States    id=cookie-banner    contains    visible
    Click    id=cookie-banner-ok
    Get Element States    id=cookie-banner    contains    hidden
