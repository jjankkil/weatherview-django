*** Settings ***
Documentation    HTTP session management keywords for the weather API.
Library          RequestsLibrary
Library          Collections
Resource         common.resource

*** Keywords ***
Create API Session
    [Documentation]    Opens a persistent HTTP session to the Django server and primes
    ...    the CSRF cookie (needed by Save Settings / Find Nearest Station — both POST
    ...    endpoints enforce Django's X-CSRFToken header check, weather/views.py:378-379).
    Create Session    weather    ${BASE_URL}    disable_warnings=True
    ${resp}=    GET On Session    weather    /    expected_status=200
    Set Suite Variable    ${CSRF_TOKEN}    ${resp.cookies}[csrftoken]

Get Stations
    ${resp}=    GET On Session    weather    /api/stations/    expected_status=any
    RETURN    ${resp}

Get Station Data
    [Arguments]    ${station_id}    ${params}=${None}
    ${resp}=    GET On Session    weather    /api/station/${station_id}/
    ...    params=${params}    expected_status=any
    RETURN    ${resp}

Get Station History
    [Arguments]    ${station_id}
    ${resp}=    GET On Session    weather    /api/station-history/${station_id}/    expected_status=any
    RETURN    ${resp}

Get Settings
    ${resp}=    GET On Session    weather    /api/settings/    expected_status=200
    RETURN    ${resp}

Save Settings
    [Arguments]    ${payload}
    ${headers}=    Create Dictionary    X-CSRFToken=${CSRF_TOKEN}
    ${resp}=    POST On Session    weather    /api/settings/save/    json=${payload}
    ...    headers=${headers}    expected_status=any
    RETURN    ${resp}

Find Nearest Station
    [Arguments]    ${lat}    ${lon}
    ${payload}=    Create Dictionary    lat=${lat}    lon=${lon}
    ${headers}=    Create Dictionary    X-CSRFToken=${CSRF_TOKEN}
    ${resp}=    POST On Session    weather    /api/nearest-station/    json=${payload}
    ...    headers=${headers}    expected_status=any
    RETURN    ${resp}
