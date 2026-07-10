import uuid

from django.db import models


def default_fields_config():
    return {
        "first_name": {"enabled": True, "required": True},
        "last_name": {"enabled": True, "required": True},
        "email": {"enabled": True, "required": True},
        "phone_number": {"enabled": True, "required": True},
        "description": {"enabled": True, "required": False},
        "age": {"enabled": False, "required": False},
    }


class LeadCaptureForm(models.Model):
    organisation = models.ForeignKey(
        "leads.Organisation",
        on_delete=models.CASCADE,
        related_name="capture_forms",
    )
    name = models.CharField(max_length=120)
    public_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    is_active = models.BooleanField(default=True)
    fields_config = models.JSONField(default=default_fields_config, blank=True)
    auto_sequence = models.ForeignKey(
        "email_engine.EmailSequence",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="capture_forms",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "name"],
                name="uniq_capture_form_org_name",
            )
        ]

    def __str__(self):
        return self.name

    def public_path(self):
        return f"/f/{self.public_key}/"
