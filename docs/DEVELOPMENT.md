# Development Guide

This guide covers local development: setting up a working copy, running the
dev server, the checks/tests to run before committing, and generating the
Doxygen API docs.

Testing is layered: `manage.py test weather` (offline, mocked HTTP) and
`pytest tests/e2e/` (Playwright browser tests) are the primary suites and
should stay green. The `tests/robot/` suite is different in purpose — it was
built as a hands-on way to learn Robot Framework, not to add new coverage.
Its API and E2E suites largely re-test the same endpoints and UI flows as the
suites above (in several cases mirroring a specific pytest test one-for-one),
just through Robot Framework's keyword-driven syntax instead of
pytest/Django's `TestCase`; its offline unit suite similarly duplicates a
subset of `weather/tests.py`'s (more thorough) coverage of
`fmi_feels_like_temperature`/`wind_direction_as_text`. 

## Local setup

```bash
git clone https://github.com/jjankkil/weatherview-django
cd weatherview-django

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate      # Linux / macOS

pip install -r requirements-dev.txt
cp .env.example .env
```

Set the required secret key in `.env`:

```env
WVD_SECRET_KEY=<generate with: python -c "from django.utils.crypto import get_random_string; print(get_random_string(50))">
```

Start the app:

```bash
# Windows PowerShell
.\startup.ps1

# Windows CMD
startup.bat

# Linux / macOS / WSL
./startup.sh
```

## Dev checks

```bash
python manage.py check
```

The development server reloads automatically on file changes.

## Testing

### Offline Django tests

```bash
python manage.py test weather
```

These tests are fast and run without network access.

### Playwright browser tests

```bash
playwright install chromium
pytest tests/e2e/
```

Coverage includes page load, station selection rendering, language switching, and language persistence.

### Robot Framework tests (optional)

`tests/robot/` has a separate Robot Framework suite (API tests against the real
endpoints, browser E2E tests, and offline unit tests of `weather/services/*`).
It's independent of the tests above and not required for everyday development —
install it only if you want to work with these tests:

```bash
pip install -r requirements-robot.txt
rfbrowser init   # only needed for the browser-based e2e/ suite; requires Node.js 20+
```

Run it from `tests/robot/`. `robot.toml`'s `output_dir` setting is only honored
by the separate `robotcode` CLI/VS Code extension (not installed here) — with
the plain `robot` runner, pass `--outputdir results` explicitly or results land
loose in `tests/robot/` (gitignored either way, but tidier in `results/`):

```bash
cd tests/robot
robot --outputdir results .                     # everything
robot --outputdir results -i smoke .            # fast subset (no network, no live external calls)
robot --outputdir results -i live .             # tests that hit the real Digitraffic/FMI APIs
robot --outputdir results api/                  # API suites only
robot --outputdir results e2e/                  # browser suites only (needs rfbrowser init)
```

### Live smoke test

```bash
python scripts/smoke_test.py
python scripts/smoke_test.py 23819
```

This test hits real Digitraffic and FMI endpoints.

## API and code documentation

Generate HTML docs with Doxygen:

```bash
doxygen Doxyfile
```

Output is generated under `docs/doxygen/html/`.

Open `docs/doxygen/html/index.html` in a browser.

Install Doxygen if needed:

- Windows: from doxygen.nl or package manager
- macOS: `brew install doxygen`
- Linux/WSL (Debian/Ubuntu): `apt-get install doxygen`
