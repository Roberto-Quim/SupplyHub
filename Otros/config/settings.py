"""Configuración base de SupplyHub.

Inspirada en el patrón de Sistema Data Analytics: secretos fuera del código,
soporte Fernet para variables sensibles y MVC con Vistas/ como templates.
"""
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent.parent

from supplyhub.security.env import get_env_bool, get_env_int, get_env_value  # noqa: E402

SECRET_KEY = get_env_value(
    "DJANGO_SECRET_KEY",
    "django-insecure-supplyhub-development-only",
    strip=False,
)
DEBUG = get_env_bool("DJANGO_DEBUG", "True")

_allowed = get_env_value("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
ALLOWED_HOSTS = [item.strip() for item in _allowed.split(",") if item.strip()]

_csrf_origins = get_env_value("DJANGO_CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = [item.strip() for item in _csrf_origins.split(",") if item.strip()]
DJANGO_ADMIN_URL = get_env_value("DJANGO_ADMIN_URL", "admin/").strip("/") + "/"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "supplyhub",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "Vistas"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "supplyhub.services.context_processors.supplyhub_context",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-mx"
TIME_ZONE = "America/Mexico_City"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "Otros" / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 28800
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_SSL_REDIRECT = get_env_bool("DJANGO_SECURE_SSL_REDIRECT", "False")
SESSION_COOKIE_SECURE = get_env_bool("DJANGO_SESSION_COOKIE_SECURE", "False")
CSRF_COOKIE_SECURE = get_env_bool("DJANGO_CSRF_COOKIE_SECURE", "False")
SECURE_HSTS_SECONDS = get_env_int("DJANGO_SECURE_HSTS_SECONDS", 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = get_env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", "False")
SECURE_HSTS_PRELOAD = get_env_bool("DJANGO_SECURE_HSTS_PRELOAD", "False")

# Feature flags que la Fase 2 conectará a los backends reales.
DATAANALYTICS_ENABLED = get_env_bool("DATAANALYTICS_ENABLED", "False")
GOOGLE_OAUTH_ENABLED = get_env_bool("GOOGLE_OAUTH_ENABLED", "False")
AD_LDAP_ENABLED = get_env_bool("AD_LDAP_ENABLED", "False")
PAYROLL_AUTH_ENABLED = get_env_bool("PAYROLL_AUTH_ENABLED", "False")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "supplyhub": {
            "handlers": ["console"],
            "level": get_env_value("DJANGO_LOG_LEVEL", "INFO").upper(),
            "propagate": False,
        }
    },
}
