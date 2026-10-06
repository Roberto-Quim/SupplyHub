"""Configuración de SupplyHub.

Paso 3: identidad corporativa basada en nómina, Google OAuth listo para activar,
menú HUB/Administración y autorización por rutas.
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

SUPPLYHUB_LOCAL_AUTH_ENABLED = DEBUG and get_env_bool(
    "SUPPLYHUB_LOCAL_AUTH_ENABLED", "True"
)
CORPORATE_USERNAME_IS_PAYROLL = get_env_bool(
    "CORPORATE_USERNAME_IS_PAYROLL", "True"
)

# ---------------------------------------------------------------------------
# Integraciones corporativas: todas opt-in.
# ---------------------------------------------------------------------------
DATAANALYTICS_ENABLED = get_env_bool("DATAANALYTICS_ENABLED", "False")
DATAANALYTICS_SP_VALIDATE = get_env_value(
    "DATAANALYTICS_SP_VALIDATE", "dbo.GetValidaUsuarioDAsp"
)
DATAANALYTICS_SP_VALIDATE_METHOD = get_env_value(
    "DATAANALYTICS_SP_VALIDATE_METHOD", "dbo.GetValidaUsuarioMetodoDAsp"
)
DATAANALYTICS_SP_ADD_ACCESS = get_env_value(
    "DATAANALYTICS_SP_ADD_ACCESS", "dbo.AddUsuarioAccesoDAsp"
)
DATAANALYTICS_SP_ALLOWED_ROUTES = get_env_value(
    "DATAANALYTICS_SP_ALLOWED_ROUTES", "dbo.GetSubmodulosPermitidosEstadoDAsp"
)

GOOGLE_OAUTH_ENABLED = get_env_bool("GOOGLE_OAUTH_ENABLED", "False")
GOOGLE_CLIENT_ID = get_env_value("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = get_env_value("GOOGLE_CLIENT_SECRET", "", strip=False)
GOOGLE_ALLOWED_DOMAIN = get_env_value("GOOGLE_ALLOWED_DOMAIN", "")

AD_LDAP_ENABLED = get_env_bool("AD_LDAP_ENABLED", "False")
AD_LDAP_SERVER_URI = get_env_value("AD_LDAP_SERVER_URI", "")
AD_LDAP_DOMAIN = get_env_value("AD_LDAP_DOMAIN", "")
AD_LDAP_USER_SEARCH_BASE_DN = get_env_value("AD_LDAP_USER_SEARCH_BASE_DN", "")
AD_LDAP_USER_SEARCH_FILTER = get_env_value(
    "AD_LDAP_USER_SEARCH_FILTER", "(sAMAccountName={username})"
)
AD_LDAP_USE_SSL = get_env_bool("AD_LDAP_USE_SSL", "True")
AD_LDAP_START_TLS = get_env_bool("AD_LDAP_START_TLS", "False")
AD_LDAP_TLS_VALIDATE = get_env_value("AD_LDAP_TLS_VALIDATE", "none").lower()

PAYROLL_AUTH_ENABLED = get_env_bool("PAYROLL_AUTH_ENABLED", "False")

# ---------------------------------------------------------------------------
# Django apps / middleware
# ---------------------------------------------------------------------------
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

if GOOGLE_OAUTH_ENABLED:
    try:
        import allauth  # noqa: F401
    except ImportError as exc:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            "GOOGLE_OAUTH_ENABLED=True pero django-allauth no está instalado. "
            "Instala requirements-auth-google.txt"
        ) from exc

    INSTALLED_APPS += [
        "django.contrib.sites",
        "allauth",
        "allauth.account",
        "allauth.socialaccount",
        "allauth.socialaccount.providers.google",
    ]
    MIDDLEWARE += ["allauth.account.middleware.AccountMiddleware"]
    SITE_ID = 1
    SOCIALACCOUNT_ADAPTER = (
        "supplyhub.authentication_login.google_oauth_adapter."
        "CorporateGoogleSocialAccountAdapter"
    )
    _google_provider = {
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online", "prompt": "select_account"},
        "OAUTH_PKCE_ENABLED": True,
    }
    # Permite activar Google solo con .env, sin guardar el Client Secret en SQLite.
    if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
        _google_provider["APP"] = {
            "client_id": GOOGLE_CLIENT_ID,
            "secret": GOOGLE_CLIENT_SECRET,
            "key": "",
        }
    SOCIALACCOUNT_PROVIDERS = {"google": _google_provider}
    SOCIALACCOUNT_STORE_TOKENS = False
    SOCIALACCOUNT_AUTO_SIGNUP = True
    ACCOUNT_EMAIL_VERIFICATION = "none"
    ACCOUNT_SIGNUP_REDIRECT_URL = "/"
    ACCOUNT_LOGOUT_REDIRECT_URL = "/login/"
    ACCOUNT_DEFAULT_HTTP_PROTOCOL = "http" if DEBUG else "https"

if AD_LDAP_ENABLED:
    try:
        import ldap3  # noqa: F401
    except ImportError as exc:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            "AD_LDAP_ENABLED=True pero ldap3 no está instalado. "
            "Instala requirements-auth-ldap.txt"
        ) from exc

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

_auth_backends = ["django.contrib.auth.backends.ModelBackend"]
if AD_LDAP_ENABLED:
    _auth_backends.insert(
        0,
        "supplyhub.authentication_login.active_directory_backend.ActiveDirectoryLDAPBackend",
    )
if GOOGLE_OAUTH_ENABLED:
    _auth_backends.append("allauth.account.auth_backends.AuthenticationBackend")
if PAYROLL_AUTH_ENABLED:
    _auth_backends.append(
        "supplyhub.authentication_login.payroll_backend.PayrollDatabaseBackend"
    )
AUTHENTICATION_BACKENDS = _auth_backends

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

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
SECURE_HSTS_INCLUDE_SUBDOMAINS = get_env_bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", "False"
)
SECURE_HSTS_PRELOAD = get_env_bool("DJANGO_SECURE_HSTS_PRELOAD", "False")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "supplyhub": {
            "handlers": ["console"],
            "level": get_env_value("DJANGO_LOG_LEVEL", "INFO").upper(),
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}
