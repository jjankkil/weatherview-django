*** Settings ***
Documentation    Offline unit tests for weather/services/* pure functions, run
...              through tests/robot/libraries/WeatherServiceLibrary.py. No Django
...              server or network access needed.
Library          ../libraries/WeatherServiceLibrary.py
Test Tags        unit    smoke

*** Test Cases ***
Feels Like Is Colder When Windy
    ${result}=    Compute Feels Like    wind=10.0    rh=50.0    temp=-5.0
    Should Be True    ${result} < -5.0

Feels Like Equals Air Temperature When Calm
    ${result}=    Compute Feels Like    wind=0.0    rh=50.0    temp=-5.0
    Should Be Equal As Numbers    ${result}    -5.0

Wind 0 Degrees Is North In Finnish
    ${text}=    Wind Degrees To Text    0    fi
    Should Be Equal    ${text}    pohjoisesta

Wind 0 Degrees Is North In English
    ${text}=    Wind Degrees To Text    0    en
    Should Be Equal    ${text}    from N

Wind None Degrees Is Empty String
    ${text}=    Wind Degrees To Text    ${None}    fi
    Should Be Equal    ${text}    ${EMPTY}
