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


class EmailTemplate(models.Model):
    organisation = models.ForeignKey(
        "leads.Organisation",
        on_delete=models.CASCADE,
        related_name="email_templates",
    )
    name = models.CharField(max_length=120)
    subject = models.CharField(max_length=255)
    body_html = models.TextField(
        help_text="HTML body. Use merge tags like {{first_name}}."
    )
    body_text = models.TextField(
        blank=True,
        help_text="Optional plain-text fallback.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "name"],
                name="uniq_email_template_org_name",
            )
        ]

    def __str__(self):
        return self.name


class Campaign(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"
        CANCELLED = "cancelled", "Cancelled"

    organisation = models.ForeignKey(
        "leads.Organisation",
        on_delete=models.CASCADE,
        related_name="campaigns",
    )
    name = models.CharField(max_length=120)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT
    )
    contact_list = models.ForeignKey(
        "leads.ContactList",
        on_delete=models.PROTECT,
        related_name="campaigns",
    )
    template = models.ForeignKey(
        EmailTemplate,
        on_delete=models.PROTECT,
        related_name="campaigns",
    )
    scheduled_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_campaigns",
    )
    # Rate limiting for Celery batch sends
    batch_size = models.PositiveIntegerField(default=25)
    batch_delay_seconds = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def can_edit(self):
        return self.status == self.Status.DRAFT

    @property
    def can_send(self):
        return self.status in {self.Status.DRAFT, self.Status.SCHEDULED}

    @property
    def can_cancel(self):
        return self.status in {
            self.Status.SCHEDULED,
            self.Status.SENDING,
        }


class CampaignRecipient(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="recipients"
    )
    lead = models.ForeignKey(
        "leads.Lead",
        on_delete=models.CASCADE,
        related_name="campaign_recipients",
    )
    outbound_email = models.ForeignKey(
        OutboundEmail,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="campaign_recipients",
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING
    )
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "lead"],
                name="uniq_campaign_lead_recipient",
            )
        ]

    def __str__(self):
        return f"{self.campaign_id}:{self.lead_id} ({self.status})"
