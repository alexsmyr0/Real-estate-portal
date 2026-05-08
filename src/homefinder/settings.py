from __future__ import annotations

from pathlib import Path

from .config import load_settings

BASE_DIR = Path(__file__).resolve().parents[2]
ENV = load_settings()

SECRET_KEY = ENV.secret_key
DEBUG = ENV.debug
ALLOWED_HOSTS = list(ENV.allowed_hosts)
CSRF_TRUSTED_ORIGINS = list(ENV.csrf_trusted_origins)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "homefinder.apps.core",
    "homefinder.apps.users",
    "homefinder.apps.properties",
    "homefinder.apps.interactions",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "homefinder.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "homefinder.wsgi.application"
ASGI_APPLICATION = "homefinder.asgi.application"

DATABASES = {
    "default": ENV.database_config,
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = ENV.time_zone
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "users.User"
EMAIL_BACKEND = ENV.email_backend
DEFAULT_FROM_EMAIL = ENV.default_from_email
EMAIL_HOST = ENV.email_host
EMAIL_PORT = ENV.email_port
EMAIL_HOST_USER = ENV.email_host_user
EMAIL_HOST_PASSWORD = ENV.email_host_password
EMAIL_USE_TLS = ENV.email_use_tls
EMAIL_USE_SSL = ENV.email_use_ssl
EMAIL_TIMEOUT = ENV.email_timeout

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
