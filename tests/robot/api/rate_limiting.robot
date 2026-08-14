*** Settings ***
Documentation    Verifies that the IP-based rate limiter (WEATHER_RATE_LIMIT,
...              default 15/m — weather/views.py _is_rate_limited) returns HTTP 429
...              once its threshold is exceeded. Station data and station history
...              share the same per-IP counter, so both count toward the same limit.
...              Run in a suite of its own so it doesn't consume the limit budget
...              of the other API suites.
Resource         ../resources/api.resource
Suite Setup      Run Keywords    Start Django Server    AND    Create API Session
Suite Teardown   Run Keywords    Delete All Sessions    AND    Stop Django Server
Test Tags        api    live

*** Variables ***
${RATE_LIMIT}    15
${STATION_ID}    1001

*** Test Cases ***
Requests Within Limit Are Accepted
    FOR    ${i}    IN RANGE    ${RATE_LIMIT}
        ${resp}=    Get Station Data    ${STATION_ID}
        Should Not Be Equal As Integers    ${resp.status_code}    429
    END

Request After Limit Returns 429
    ${resp}=    Get Station Data    ${STATION_ID}
    Should Be Equal As Integers    ${resp.status_code}    429
    Dictionary Should Contain Key    ${resp.json()}    error
