import hashlib
import secrets

from django.conf import settings
from django.db import models


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_api_token() -> str:
    return secrets.token_urlsafe(32)


class APIToken(models.Model):
    organisation = models.ForeignKey(
        "leads.Organisation",
        on_delete=models.CASCADE,
        related_name="api_tokens",
    )
    name = models.CharField(max_length=120)
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    prefix = models.CharField(max_length=12, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_api_tokens",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.prefix}…)"

    @property
    def is_active(self):
        return self.revoked_at is None

    @classmethod
    def create_for_org(cls, organisation, *, name: str, created_by=None):
        raw = generate_api_token()
        return cls.objects.create(
            organisation=organisation,
            name=name,
            token_hash=hash_token(raw),
            prefix=raw[:8],
            created_by=created_by,
        ), raw

    @classmethod
    def resolve(cls, raw_token: str):
        if not raw_token:
            return None
        return (
            cls.objects.select_related("organisation")
            .filter(token_hash=hash_token(raw_token), revoked_at__isnull=True)
            .first()
        )
