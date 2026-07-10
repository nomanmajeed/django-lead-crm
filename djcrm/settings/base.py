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
LOGIN_REDIRECT_URL = "/app/"
LOGOUT_REDIRECT_URL = "landing_page"

INSTALLED_APPS = [
    # Project Apps
    "leads",
    "agents",
    "email_engine",
    "billing",
    "notifications",
    "audit",
    "capture",
    "public_api",
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
    "leads.middleware.TenantMiddleware",
    "leads.role_space.RoleSpaceMiddleware",
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
                "leads.context_processors.tenant",
                "notifications.context_processors.notifications_badge",
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

# --- Email engine ---
# console | smtp | sendgrid | postmark
EMAIL_PROVIDER = env("EMAIL_PROVIDER", default="console")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@leadcrm.local")
EMAIL_WEBHOOK_SECRET = env("EMAIL_WEBHOOK_SECRET", default="")
SENDGRID_API_KEY = env("SENDGRID_API_KEY", default="")
POSTMARK_SERVER_TOKEN = env("POSTMARK_SERVER_TOKEN", default="")
# When True, queue via Celery; local settings force eager execution.
EMAIL_ASYNC = env.bool("EMAIL_ASYNC", default=True)
# One-shot campaign batching / rate limiting
CAMPAIGN_BATCH_SIZE = env.int("CAMPAIGN_BATCH_SIZE", default=25)
CAMPAIGN_BATCH_DELAY_SECONDS = env.int("CAMPAIGN_BATCH_DELAY_SECONDS", default=1)
# Absolute base URL for open/click/unsubscribe links in emails
PUBLIC_BASE_URL = env("PUBLIC_BASE_URL", default="http://127.0.0.1:8001")

# --- Stripe billing ---
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY", default="")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")
STRIPE_PRICE_PRO = env("STRIPE_PRICE_PRO", default="")
STRIPE_PRICE_BUSINESS = env("STRIPE_PRICE_BUSINESS", default="")
# When True (and no Stripe secret), billing POST can set plan directly for local/dev.
STRIPE_BILLING_SIMULATE = env.bool("STRIPE_BILLING_SIMULATE", default=True)

CAPTURE_FORM_RATE_LIMIT = env.int("CAPTURE_FORM_RATE_LIMIT", default=20)
CAPTURE_FORM_RATE_WINDOW = env.int("CAPTURE_FORM_RATE_WINDOW", default=3600)

# --- Celery / Redis ---
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=CELERY_BROKER_URL)
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
