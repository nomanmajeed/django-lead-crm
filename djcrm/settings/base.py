"""
Shared Django settings for all environments.

Environment-specific modules: ``local`` (default) and ``prod``.
Select via ``DJANGO_ENV=local|prod`` (see ``djcrm.settings`` package).
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)

# Load project-root .env when present (or when READ_DOT_ENV_FILE=True).
_env_file = BASE_DIR / ".env"
if env.bool("READ_DOT_ENV_FILE", default=_env_file.exists()):
    environ.Env.read_env(_env_file)

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")

AUTH_USER_MODEL = "leads.User"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "/leads"
LOGOUT_REDIRECT_URL = "landing_page"

INSTALLED_APPS = [
    # Project Apps
    "leads",
    "agents",
    # Third party apps
    "crispy_forms",
    "crispy_tailwind",
    # Default Django Apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"
CRISPY_TEMPLATE_PACK = "tailwind"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "djcrm.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "djcrm.wsgi.application"

# PostgreSQL only — set DATABASE_URL (see .env.example)
DATABASES = {"default": env.db("DATABASE_URL")}

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "static_root"
