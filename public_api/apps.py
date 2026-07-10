import hashlib
import secrets

from django.apps import AppConfig


class PublicApiConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "public_api"
    verbose_name = "Public API"
