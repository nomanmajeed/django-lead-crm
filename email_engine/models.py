from django.conf import settings
from django.db import models


class OutboundEmail(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    organisation = models.ForeignKey(
        "leads.Organisation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="outbound_emails",
    )
    to_email = models.EmailField()
    from_email = models.EmailField()
    subject = models.CharField(max_length=255)
    body_text = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    provider = models.CharField(max_length=32, default="console")
    provider_message_id = models.CharField(max_length=255, blank=True, db_index=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.QUEUED
    )
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject} → {self.to_email}"


class EmailDeliveryEvent(models.Model):
    class EventType(models.TextChoices):
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        BOUNCE = "bounce", "Bounce"
        COMPLAINT = "complaint", "Complaint"
        OPEN = "open", "Open"
        CLICK = "click", "Click"
        FAILED = "failed", "Failed"

    outbound_email = models.ForeignKey(
        OutboundEmail,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="events",
    )
    provider = models.CharField(max_length=32)
    provider_message_id = models.CharField(max_length=255, blank=True, db_index=True)
    event_type = models.CharField(max_length=32, choices=EventType.choices)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.event_type} ({self.provider})"


def default_from_email():
    return getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@leadcrm.local")
