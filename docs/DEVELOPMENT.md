# Development Guide

## Local setup

```bash
git clone https://github.com/jjankkil/weatherview-django
cd weatherview-django

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate      # Linux / macOS

pip install -r requirements.txt
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
pip install -r requirements-dev.txt
playwright install chromium
pytest tests/e2e/
```

Coverage includes page load, station selection rendering, language switching, and language persistence.

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
