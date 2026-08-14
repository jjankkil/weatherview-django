*** Settings ***
Documentation    Tests for GET /api/settings/ and POST /api/settings/save/.
...              Session-based only — no external API calls, so no "live" tag needed.
Resource         ../resources/api.resource
Suite Setup      Run Keywords    Start Django Server    AND    Create API Session
Suite Teardown   Run Keywords    Delete All Sessions    AND    Stop Django Server
Test Tags        api

*** Test Cases ***
Default Settings Are Returned
    ${resp}=    Get Settings
    ${body}=    Set Variable    ${resp.json()}
    Dictionary Should Contain Key    ${body}    current_station_id
    Dictionary Should Contain Key    ${body}    current_station_name
    Dictionary Should Contain Key    ${body}    language
    Dictionary Should Contain Key    ${body}    show_camera
    Dictionary Should Contain Key    ${body}    follow_location
    Dictionary Should Contain Key    ${body}    show_history
    Dictionary Should Contain Key    ${body}    history_hours
    Should Be Equal        ${body}[language]      fi
    Should Be Equal        ${body}[current_station_id]    ${None}
    Should Be True          ${body}[show_camera]
    Should Not Be True      ${body}[follow_location]
    Should Be True          ${body}[show_history]
    Should Be Equal As Integers    ${body}[history_hours]    12

Save And Retrieve Language Setting
    ${payload}=    Create Dictionary    language=en
    Save Settings    ${payload}
    ${resp}=    Get Settings
    Should Be Equal    ${resp.json()}[language]    en

Reject Unknown Language
    ${payload}=    Create Dictionary    language=de
    ${resp}=    Save Settings    ${payload}
    Should Be Equal As Integers    ${resp.status_code}    400
    Dictionary Should Contain Key    ${resp.json()}    error

History Hours Within Range Is Accepted
    [Documentation]    history_hours must be sent as a JSON integer — ${6} (not the
    ...                string "6") so RequestsLibrary serializes it as a number;
    ...                the view's isinstance(val, int) check rejects strings.
    ${payload}=    Create Dictionary    history_hours=${6}
    ${resp}=    Save Settings    ${payload}
    Should Be Equal As Integers    ${resp.status_code}    200
    ${resp}=    Get Settings
    Should Be Equal As Integers    ${resp.json()}[history_hours]    6

Reject History Hours Below Minimum
    ${payload}=    Create Dictionary    history_hours=${0}
    ${resp}=    Save Settings    ${payload}
    Should Be Equal As Integers    ${resp.status_code}    400
    Dictionary Should Contain Key    ${resp.json()}    error

Reject History Hours Above Maximum
    ${payload}=    Create Dictionary    history_hours=${999}
    ${resp}=    Save Settings    ${payload}
    Should Be Equal As Integers    ${resp.status_code}    400
    Dictionary Should Contain Key    ${resp.json()}    error

Reject Non Boolean Show Camera
    ${payload}=    Create Dictionary    show_camera=notabool
    ${resp}=    Save Settings    ${payload}
    Should Be Equal As Integers    ${resp.status_code}    400

Settings Save Requires POST
    ${resp}=    GET On Session    weather    /api/settings/save/    expected_status=any
    Should Be Equal As Integers    ${resp.status_code}    405
