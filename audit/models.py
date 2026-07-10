from django.conf import settings
from django.db import models


class AuditEntry(models.Model):
    class ObjectType(models.TextChoices):
        LEAD = "lead", "Lead"
        CAMPAIGN = "campaign", "Campaign"
        TEAM = "team", "Team"
        OTHER = "other", "Other"

    organisation = models.ForeignKey(
        "leads.Organisation",
        on_delete=models.CASCADE,
        related_name="audit_entries",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_entries",
    )
    action = models.CharField(max_length=64)
    object_type = models.CharField(
        max_length=32, choices=ObjectType.choices, default=ObjectType.OTHER
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    object_repr = models.CharField(max_length=255, blank=True, default="")
    summary = models.CharField(max_length=500)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "audit entries"

    def __str__(self):
        return f"{self.action}: {self.summary}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Audit entries are append-only")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Audit entries cannot be deleted")
