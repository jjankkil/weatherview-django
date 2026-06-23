"""Pytest fixtures for Playwright e2e tests.

Starts a Django development server once per session and exposes its URL as
the ``base_url`` fixture consumed by pytest-playwright's ``page`` fixture.

External API calls (Digitraffic, FMI) are intercepted by ``page.route()``
mocks inside each test, so no real network access or Redis is required.
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from playwright.sync_api import Page

_PORT = 18765
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def _django_server():
    """Start manage.py runserver; yield the base URL; terminate after the session."""
    env = {
        **os.environ,
        "WVD_SECRET_KEY": "playwright-e2e-test-key-DO-NOT-USE-IN-PROD",
        "WVD_DEBUG": "True",
        "WVD_ALLOWED_HOSTS": "127.0.0.1,localhost",
    }
    proc = subprocess.Popen(
        [
            sys.executable,
            "manage.py",
            "runserver",
            f"127.0.0.1:{_PORT}",
            "--noreload",
        ],
        cwd=_PROJECT_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", _PORT), timeout=1):
                break
        except OSError:
            time.sleep(0.3)
    else:
        proc.kill()
        raise RuntimeError(f"Django server did not start on port {_PORT}")

    yield f"http://127.0.0.1:{_PORT}"

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="session")
def base_url(_django_server):  # noqa: F811 — overrides pytest-playwright default
    return _django_server


@pytest.fixture(autouse=True)
def _auto_dismiss_cookie_banner(page: Page, request) -> None:
    """Pre-set the cookie consent flag in localStorage for every test.

    Tests that explicitly want to see the banner (e.g. the banner smoke test)
    can opt out by marking with ``@pytest.mark.show_cookie_banner``.
    """
    if request.node.get_closest_marker("show_cookie_banner"):
        return
    page.add_init_script("localStorage.setItem('cookie_consent_v1', '1')")
