"""Local / development settings."""

from .base import *  # noqa: F403
from .base import env

DEBUG = env.bool("DEBUG", default=True)

ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1"],
)

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
EMAIL_PROVIDER = env("EMAIL_PROVIDER", default="console")
# Local: run Celery tasks inline so Redis is optional for day-to-day work.
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=True)

# Admin enabled for local development.
DJANGO_ADMIN_ENABLED = env.bool("DJANGO_ADMIN_ENABLED", default=True)
