*** Settings ***
Documentation    Tests for POST /api/nearest-station/.
Resource         ../resources/api.resource
Suite Setup      Run Keywords    Start Django Server    AND    Create API Session
Suite Teardown   Run Keywords    Delete All Sessions    AND    Stop Django Server
Test Tags        api

*** Test Cases ***
Valid Coordinates Return A Station
    [Documentation]    Uses the real (live) station list to resolve the nearest station.
    [Tags]    live
    ${resp}=    Find Nearest Station    60.198    24.932
    Should Be Equal As Integers    ${resp.status_code}    200
    ${body}=    Set Variable    ${resp.json()}
    Dictionary Should Contain Key    ${body}    id
    Dictionary Should Contain Key    ${body}    name
    Dictionary Should Contain Key    ${body}    formatted_name
    Dictionary Should Contain Key    ${body}    lat
    Dictionary Should Contain Key    ${body}    lon

Missing Lat Returns 400
    ${headers}=    Create Dictionary    X-CSRFToken=${CSRF_TOKEN}
    ${payload}=    Create Dictionary    lon=24.932
    ${resp}=    POST On Session    weather    /api/nearest-station/    json=${payload}
    ...    headers=${headers}    expected_status=any
    Should Be Equal As Integers    ${resp.status_code}    400
    Dictionary Should Contain Key    ${resp.json()}    error

Non Numeric Coordinates Return 400
    ${headers}=    Create Dictionary    X-CSRFToken=${CSRF_TOKEN}
    ${payload}=    Create Dictionary    lat=notanumber    lon=24.932
    ${resp}=    POST On Session    weather    /api/nearest-station/    json=${payload}
    ...    headers=${headers}    expected_status=any
    Should Be Equal As Integers    ${resp.status_code}    400

GET With Query Params Is Also Accepted
    [Documentation]    api_nearest_station allows both GET and POST (views.py @require_http_methods(["GET", "POST"])).
    [Tags]    live
    ${resp}=    GET On Session    weather    /api/nearest-station/    params=lat=60.198&lon=24.932    expected_status=any
    Should Be Equal As Integers    ${resp.status_code}    200
