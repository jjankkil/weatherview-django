## @file settings.py
#  @brief Django settings for the weatherview_project application.
#
#  All runtime-sensitive values are read from environment variables so that
#  no secrets need to be committed to the repository.  The required variable
#  is `WVD_SECRET_KEY`; optional variables and their defaults are listed below.
#
#  | Variable | Default | Purpose |
#  |---|---|---|
#  | WVD_SECRET_KEY | *(required)* | Django cryptographic secret key |
#  | WVD_DEBUG | `False` | Enable Django debug mode |
#  | WVD_ALLOWED_HOSTS | `*,localhost,127.0.0.1` | Comma-separated allowed host list |
#  | WVD_CSRF_TRUSTED_ORIGINS | *(unset)* | Comma-separated scheme-qualified origins trusted for CSRF (e.g. `https://weather.example.com`) |
#  | WVD_SESSION_COOKIE_AGE | `604800` (7 days) | Session lifetime in seconds |
#  | WVD_SECURE_HSTS_SECONDS | `31536000` (prod) / `0` (debug) | HSTS max-age |
#  | WEATHER_RATE_LIMIT | `15/m` | Rate limit for weather API endpoint (per IP), e.g. "15/m" |
#  | WVD_REDIS_URL | *(unset)* | Redis URL for caching. When unset: LocMemCache (single-worker dev). When set: RedisCache (multi-worker prod). |
#
#  @author Jari Jankkila
#  @date 2026

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  ##< Absolute path to the repository root.


def load_environment_from_dotenv(env_path: Path | None = None) -> dict[str, str]:
    """Load environment variables from a .env file when present.

    Values from the shell are preserved; only missing variables are populated from the file.
    """
    resolved_path = env_path or BASE_DIR / ".env"
    if not resolved_path.exists():
        return {}

    loaded_values: dict[str, str] = {}
    for raw_line in resolved_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
            value = value[1:-1]

        if " #" in value:
            value = value.split(" #", 1)[0].rstrip()

        os.environ.setdefault(key, value)
        loaded_values[key] = value

    return loaded_values


load_environment_from_dotenv()

SECRET_KEY = os.environ["WVD_SECRET_KEY"]  ##< Django cryptographic secret key. Set via WVD_SECRET_KEY env var (required).

DEBUG = os.getenv("WVD_DEBUG", "False") == "True"  ##< Enable Django debug mode. Set WVD_DEBUG=True to activate.

ALLOWED_HOSTS = os.getenv("WVD_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")  ##< Comma-separated list of allowed hostnames. Set via WVD_ALLOWED_HOSTS.

CSRF_TRUSTED_ORIGINS = list(  ##< Scheme-qualified origins trusted for unsafe (CSRF-checked) requests. Set via WVD_CSRF_TRUSTED_ORIGINS (comma-separated, each including https://). Empty by default (LAN-only deployments don't need it).
    filter(None, os.getenv("WVD_CSRF_TRUSTED_ORIGINS", "").split(","))
)

WEATHER_RATE_LIMIT = os.getenv("WEATHER_RATE_LIMIT", "15/m")  ##< Rate limit for weather API endpoint (per IP). Sliding-window format: "<count>/<unit>" where unit is s/m/h/d.

TRUSTED_PROXY_IPS: frozenset = frozenset(  ##< Set of reverse-proxy IP addresses whose X-Forwarded-For header is trusted. Set via WVD_TRUSTED_PROXY_IPS (comma-separated). Empty by default (direct connections only).
    filter(None, os.getenv("WVD_TRUSTED_PROXY_IPS", "").split(","))
)

INSTALLED_APPS = [  ##< Django applications enabled for this project.
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "weather",
]

MIDDLEWARE = [  ##< Ordered list of Django middleware classes.
    "django.middleware.security.SecurityMiddleware",
    "weatherview_project.middleware.PermissionsPolicyMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "weatherview_project.urls"  ##< Python module path to the root URL configuration.

TEMPLATES = [  ##< Django template engine configuration.
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.csrf",
            ],
        },
    },
]

WSGI_APPLICATION = "weatherview_project.wsgi.application"  ##< WSGI application callable path.

# No database needed — sessions stored in signed cookies
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"  ##< Use signed cookies for sessions; no database required.

SESSION_COOKIE_AGE = int(os.getenv("WVD_SESSION_COOKIE_AGE", str(60 * 60 * 24 * 7)))  ##< Session lifetime in seconds (default 7 days). Set via WVD_SESSION_COOKIE_AGE.
SESSION_COOKIE_SECURE = not DEBUG  ##< Transmit session cookie over HTTPS only (disabled in debug mode).
SESSION_COOKIE_HTTPONLY = True  ##< Prevent JavaScript access to the session cookie.

CSRF_COOKIE_SECURE = not DEBUG  ##< Transmit CSRF cookie over HTTPS only (disabled in debug mode).
CSRF_COOKIE_HTTPONLY = True  ##< Prevent JavaScript access to the CSRF cookie.

SECURE_SSL_REDIRECT = False  ##< Nginx handles HTTP→HTTPS redirect; keep Django redirect off to avoid redirect loops.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")  ##< Trust X-Forwarded-Proto header from Nginx so Django treats requests as HTTPS.
SECURE_HSTS_SECONDS = int(  ##< HSTS max-age in seconds. Set WVD_SECURE_HSTS_SECONDS to override; defaults to 1 year in production.
    os.getenv("WVD_SECURE_HSTS_SECONDS", "0" if DEBUG else "31536000")
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG  ##< Apply HSTS policy to all subdomains in production.
SECURE_HSTS_PRELOAD = not DEBUG  ##< Opt into HSTS preload list in production.
SECURE_CONTENT_TYPE_NOSNIFF = True  ##< Prevent MIME-type sniffing by the browser.
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"  ##< Limit Referer header to origin only on cross-origin requests.

def build_cache_settings(redis_url: str | None) -> dict:
    """Build a cache configuration that degrades safely when Redis is unavailable."""
    if redis_url:
        return {
            "default": {
                "BACKEND": "django_redis.cache.RedisCache",
                "LOCATION": redis_url,
                "OPTIONS": {
                    "CLIENT_CLASS": "django_redis.client.DefaultClient",
                    "IGNORE_EXCEPTIONS": True,
                },
                "TIMEOUT": 300,  # station list cached for 5 minutes
            }
        }

    return {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "TIMEOUT": 300,  # station list cached for 5 minutes
        }
    }


_redis_url = os.getenv("WVD_REDIS_URL")  ##< Redis URL; None when WVD_REDIS_URL is unset (falls back to LocMemCache).
CACHES = build_cache_settings(_redis_url)

LANGUAGE_CODE = "fi"  ##< Default language code (Finnish).
TIME_ZONE = "Europe/Helsinki"  ##< Default time zone for the application.
USE_I18N = False  ##< Disable Django's translation framework (not needed for this project).
USE_TZ = True  ##< Store datetimes as timezone-aware values.

STATIC_URL = "/static/"  ##< URL prefix for static assets.
STATIC_ROOT = BASE_DIR / "staticfiles"  ##< Filesystem path where `collectstatic` copies files.

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"  ##< Default primary key type for models.

LOGGING = {  ##< Logging configuration: WARNING+ to stderr console.
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "[%(asctime)s] %(levelname)s %(name)s %(message)s",
            "datefmt": "%d.%b.%Y %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
}
