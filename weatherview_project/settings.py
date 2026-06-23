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
#  | WVD_SESSION_COOKIE_AGE | `1209600` (14 days) | Session lifetime in seconds |
#  | WVD_SECURE_HSTS_SECONDS | `31536000` (prod) / `0` (debug) | HSTS max-age |
#  | WEATHER_RATE_LIMIT | `15/m` | Rate limit for weather API endpoint (per IP), e.g. "15/m" |
#  | WVD_REDIS_URL | *(unset)* | Redis URL for caching. When unset: LocMemCache (single-worker dev). When set: RedisCache (multi-worker prod). |
#
#  @author Jari Jankkila
#  @date 2026

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  ##< Absolute path to the repository root.

SECRET_KEY = os.environ["WVD_SECRET_KEY"]  ##< Django cryptographic secret key. Set via WVD_SECRET_KEY env var (required).

DEBUG = os.getenv("WVD_DEBUG", "False") == "True"  ##< Enable Django debug mode. Set WVD_DEBUG=True to activate.

ALLOWED_HOSTS = os.getenv("WVD_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")  ##< Comma-separated list of allowed hostnames. Set via WVD_ALLOWED_HOSTS.

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
            ],
        },
    },
]

WSGI_APPLICATION = "weatherview_project.wsgi.application"  ##< WSGI application callable path.

# No database needed — sessions stored in signed cookies
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"  ##< Use signed cookies for sessions; no database required.

SESSION_COOKIE_AGE = int(os.getenv("WVD_SESSION_COOKIE_AGE", str(60 * 60 * 24 * 14)))  ##< Session lifetime in seconds (default 14 days). Set via WVD_SESSION_COOKIE_AGE.
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

_redis_url = os.getenv("WVD_REDIS_URL")  ##< Redis URL; None when WVD_REDIS_URL is unset (falls back to LocMemCache).

if _redis_url:  ##< Use Redis when WVD_REDIS_URL is set (multi-worker production).
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": _redis_url,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
            "TIMEOUT": 300,  # station list cached for 5 minutes
        }
    }
else:  ##< Fall back to LocMemCache for single-worker development (no Redis required).
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "TIMEOUT": 300,  # station list cached for 5 minutes
        }
    }

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
