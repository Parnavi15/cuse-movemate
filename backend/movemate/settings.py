"""Django settings for Cuse-MoveMate."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-change-me-before-you-deploy")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    "core",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "movemate.urls"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

WSGI_APPLICATION = "movemate.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_USER_MODEL = "core.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 6}},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/New_York"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

# Uploaded listing photos. Fine for a demo; production would use S3 or similar.
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}
if DEBUG:
    REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"].append(
        "rest_framework.renderers.BrowsableAPIRenderer"
    )

# ---------------------------------------------------------------------------
# Email. Set EMAIL_HOST_USER and EMAIL_HOST_PASSWORD and verification codes go
# to real inboxes. Leave them unset and Django prints the message to the
# console instead, so the project still runs without a mail account.
# ---------------------------------------------------------------------------
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "0") == "1"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_TIMEOUT = 15
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    f"Cuse-MoveMate <{EMAIL_HOST_USER}>" if EMAIL_HOST_USER else "no-reply@cuse-movemate.local",
)
# Where email links point. Change when you deploy.
APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:5173")
APP_VERSION = "v18"

EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend"
    if EMAIL_HOST_USER
    else "django.core.mail.backends.console.EmailBackend"
)

# Optional. With a key, geocoding uses Google Maps; without one it falls back
# to OpenStreetMap's Nominatim, which needs no account. Either way the call is
# made server-side so the key never reaches the browser.
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

# ---------------------------------------------------------------------------
# Who is allowed in.
#
# Cuse-MoveMate is a campus product, so account creation is restricted to these
# email domains. Subdomains count too (g.syr.edu, mail.syr.edu). Override with
# MOVEMATE_STUDENT_DOMAINS="syr.edu,esf.edu" to open it to another campus.
# ---------------------------------------------------------------------------
ALLOWED_STUDENT_EMAIL_DOMAINS = [
    d for d in os.environ.get("MOVEMATE_STUDENT_DOMAINS", "syr.edu").split(",") if d.strip()
]

# Unverified accounts can browse. Listing, claiming and redeeming need a
# confirmed campus mailbox. Set to 0 only if you are demoing without email.
REQUIRE_VERIFIED_STUDENT = os.environ.get("MOVEMATE_REQUIRE_VERIFIED", "1") == "1"

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CORS_ALLOW_CREDENTIALS = True
