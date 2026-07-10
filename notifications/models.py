from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Kind(models.TextChoices):
        ASSIGNMENT = "assignment", "Assignment"
        INVITE = "invite", "Invite"
        CAMPAIGN = "campaign", "Campaign"
        BILLING = "billing", "Billing"

    organisation = models.ForeignKey(
        "leads.Organisation",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    kind = models.CharField(max_length=32, choices=Kind.choices)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True, default="")
    link_url = models.CharField(max_length=500, blank=True, default="")
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} → {self.recipient_id}"

    @property
    def is_read(self):
        return self.read_at is not None
