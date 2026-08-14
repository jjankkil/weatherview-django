*** Settings ***
Documentation    Django dev-server lifecycle and shared variables.
Library          Process
Library          OperatingSystem

*** Variables ***
${BASE_URL}             http://127.0.0.1:18765
${SERVER_PORT}          18765
${FIXTURE_SERVER_PORT}  18766

*** Keywords ***
Start Django Server
    [Documentation]    Starts `manage.py runserver` and waits until the port is open.
    ...    Uses the same port and env vars as tests/e2e/conftest.py so the two
    ...    suites are not run concurrently (see docs/private/ROBOTFRAMEWORK_PLAN.md §8).
    ...    Talks to the real Digitraffic/FMI APIs — used by the API suites, which
    ...    tag their live-data assertions with "live".
    ...    WVD_REDIS_URL is forced empty (LocMemCache) so caching/rate-limiting
    ...    behave deterministically even if the developer's local .env points
    ...    WVD_REDIS_URL at a Redis instance that isn't running — Django's
    ...    django-redis client has IGNORE_EXCEPTIONS=True, which would otherwise
    ...    silently no-op every cache read/write (see weatherview_project/settings.py
    ...    build_cache_settings) and make rate limiting never trigger.
    ${python}=    Evaluate    sys.executable    modules=sys
    Start Process
    ...    ${python}    manage.py    runserver    127.0.0.1:${SERVER_PORT}    --noreload
    ...    cwd=${CURDIR}/../../..    alias=django
    ...    env:WVD_SECRET_KEY=robot-test-key-DO-NOT-USE-IN-PROD
    ...    env:WVD_DEBUG=True
    ...    env:WVD_ALLOWED_HOSTS=127.0.0.1,localhost
    ...    env:WVD_REDIS_URL=
    ...    stdout=${OUTPUT_DIR}/django-stdout.log    stderr=${OUTPUT_DIR}/django-stderr.log
    Wait Until Keyword Succeeds    20s    0.5s    TCP Port Should Be Open    127.0.0.1    ${SERVER_PORT}

Start Fixture Server
    [Documentation]    Starts the local Digitraffic-shaped fixture HTTP server
    ...    (tests/robot/fixtures/fixture_server.py) used to give the E2E browser
    ...    suites deterministic station/weather data without hitting the internet.
    ${python}=    Evaluate    sys.executable    modules=sys
    Start Process
    ...    ${python}    ${CURDIR}/../fixtures/fixture_server.py    ${FIXTURE_SERVER_PORT}
    ...    alias=fixture_server
    ...    stdout=${OUTPUT_DIR}/fixture-server-stdout.log    stderr=${OUTPUT_DIR}/fixture-server-stderr.log
    Wait Until Keyword Succeeds    10s    0.2s    TCP Port Should Be Open    127.0.0.1    ${FIXTURE_SERVER_PORT}

Start Django Server With Fixtures
    [Documentation]    Starts the fixture server first, then Django pointed at it via
    ...    WVD_DIGITRAFFIC_BASE_URL, so E2E browser suites see deterministic data
    ...    (FMI forecast calls still degrade gracefully to an empty forecast — see
    ...    WeatherService.build_full_weather_response).
    Start Fixture Server
    ${python}=    Evaluate    sys.executable    modules=sys
    Start Process
    ...    ${python}    manage.py    runserver    127.0.0.1:${SERVER_PORT}    --noreload
    ...    cwd=${CURDIR}/../../..    alias=django
    ...    env:WVD_SECRET_KEY=robot-test-key-DO-NOT-USE-IN-PROD
    ...    env:WVD_DEBUG=True
    ...    env:WVD_ALLOWED_HOSTS=127.0.0.1,localhost
    ...    env:WVD_DIGITRAFFIC_BASE_URL=http://127.0.0.1:${FIXTURE_SERVER_PORT}
    ...    env:WVD_REDIS_URL=
    ...    stdout=${OUTPUT_DIR}/django-stdout.log    stderr=${OUTPUT_DIR}/django-stderr.log
    Wait Until Keyword Succeeds    20s    0.5s    TCP Port Should Be Open    127.0.0.1    ${SERVER_PORT}

Stop Django Server
    Terminate Process    django    kill=True

Stop Fixture Server
    Terminate Process    fixture_server    kill=True

TCP Port Should Be Open
    [Documentation]    Fails until the TCP connection succeeds — used by Wait Until Keyword Succeeds.
    [Arguments]    ${host}    ${port}
    Evaluate    __import__('socket').create_connection(('${host}', ${port}), timeout=1).close()
