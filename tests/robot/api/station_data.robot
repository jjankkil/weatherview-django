*** Settings ***
Documentation    Tests for GET /api/station/<id>/.
Resource         ../resources/api.resource
Suite Setup      Run Keywords    Start Django Server    AND    Create API Session
Suite Teardown   Run Keywords    Delete All Sessions    AND    Stop Django Server
Test Tags        api

*** Variables ***
${VALID_STATION_ID}      1001
${INVALID_STATION_ID}    9999999

*** Test Cases ***
Valid Station Returns 200 With Weather Fields
    [Documentation]    Hits the real Digitraffic/FMI stack for station 1001 (Helsinki / Pasila).
    [Tags]    live
    ${resp}=    Get Station Data    ${VALID_STATION_ID}
    Should Be Equal As Integers    ${resp.status_code}    200
    ${body}=    Set Variable    ${resp.json()}
    Dictionary Should Contain Key    ${body}    temperature
    Dictionary Should Contain Key    ${body}    wind_speed
    Dictionary Should Contain Key    ${body}    humidity
    Dictionary Should Contain Key    ${body}    seconds_until_next_update

Internal Field Is Stripped From Response
    [Documentation]    _next_update_at is an internal cache field and must never
    ...                reach the client (weather/views.py api_station_data).
    [Tags]    live
    ${resp}=    Get Station Data    ${VALID_STATION_ID}
    Dictionary Should Not Contain Key    ${resp.json()}    _next_update_at

Unknown Station Returns 502
    [Documentation]    Station lookup uses the real (live) station list — an ID
    ...                absent from it triggers the "not found" error path.
    [Tags]    live
    ${resp}=    Get Station Data    ${INVALID_STATION_ID}
    Should Be Equal As Integers    ${resp.status_code}    502
    Dictionary Should Contain Key    ${resp.json()}    error
