*** Settings ***
Documentation    Tests for GET /api/stations/. Hits the real FMI/Digitraffic
...              station list, so results are tagged "live" and internet
...              access is required.
Resource         ../resources/api.resource
Suite Setup      Run Keywords    Start Django Server    AND    Create API Session
Suite Teardown   Run Keywords    Delete All Sessions    AND    Stop Django Server
Test Tags        api    live

*** Test Cases ***
Stations Endpoint Returns 200
    ${resp}=    Get Stations
    Should Be Equal As Integers    ${resp.status_code}    200

Response Contains Stations Key
    ${resp}=    Get Stations
    Dictionary Should Contain Key    ${resp.json()}    stations

Each Station Has Required Fields
    ${resp}=    Get Stations
    ${stations}=    Set Variable    ${resp.json()}[stations]
    Should Not Be Empty    ${stations}
    FOR    ${station}    IN    @{stations}
        Dictionary Should Contain Key    ${station}    id
        Dictionary Should Contain Key    ${station}    name
        Dictionary Should Contain Key    ${station}    formatted_name
        Dictionary Should Contain Key    ${station}    lat
        Dictionary Should Contain Key    ${station}    lon
    END

Station IDs Are Positive Integers
    ${resp}=    Get Stations
    ${stations}=    Set Variable    ${resp.json()}[stations]
    FOR    ${station}    IN    @{stations}
        Should Be True    ${station}[id] > 0
    END
