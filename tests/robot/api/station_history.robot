*** Settings ***
Documentation    Tests for GET /api/station-history/<id>/. Mirrors station_data.robot.
...              Response shape is temp_series / precip_series / has_precipitation
...              (see WeatherService.get_station_history) — note the endpoint's own
...              docstring in weather/views.py describes a differently-shaped
...              "history" list, but the actual implementation returns this shape.
Resource         ../resources/api.resource
Suite Setup      Run Keywords    Start Django Server    AND    Create API Session
Suite Teardown   Run Keywords    Delete All Sessions    AND    Stop Django Server
Test Tags        api

*** Variables ***
${VALID_STATION_ID}      1001
${INVALID_STATION_ID}    9999999

*** Test Cases ***
Valid Station Returns 200 With History Fields
    [Tags]    live
    ${resp}=    Get Station History    ${VALID_STATION_ID}
    Should Be Equal As Integers    ${resp.status_code}    200
    ${body}=    Set Variable    ${resp.json()}
    Dictionary Should Contain Key    ${body}    temp_series
    Dictionary Should Contain Key    ${body}    precip_series
    Dictionary Should Contain Key    ${body}    has_precipitation

Temp Series Entries Have Time And Temperature Keys
    [Tags]    live
    ${resp}=    Get Station History    ${VALID_STATION_ID}
    ${series}=    Set Variable    ${resp.json()}[temp_series]
    FOR    ${entry}    IN    @{series}
        Dictionary Should Contain Key    ${entry}    time
        Dictionary Should Contain Key    ${entry}    temperature
    END

Unknown Station Returns 502
    [Tags]    live
    ${resp}=    Get Station History    ${INVALID_STATION_ID}
    Should Be Equal As Integers    ${resp.status_code}    502
    Dictionary Should Contain Key    ${resp.json()}    error
