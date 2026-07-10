from django.conf import settings
from django.db import models


class OutboundEmail(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SUPPRESSED = "suppressed", "Suppressed"
        QUOTA_EXCEEDED = "quota", "Quota exceeded"

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
    tracking_token = models.UUIDField(null=True, blank=True, unique=True, db_index=True)
    tracking_enabled = models.BooleanField(default=False)
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
        UNSUBSCRIBE = "unsubscribe", "Unsubscribe"

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


class EmailSuppression(models.Model):
    """Org-level suppressed addresses (expanded in tracking/compliance ticket)."""

    organisation = models.ForeignKey(
        "leads.Organisation",
        on_delete=models.CASCADE,
        related_name="email_suppressions",
    )
    email = models.EmailField()
    reason = models.CharField(max_length=64, blank=True, default="unsubscribe")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "email"],
                name="uniq_email_suppression_org_email",
            )
        ]

    def __str__(self):
        return self.email


class EmailSequence(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    organisation = models.ForeignKey(
        "leads.Organisation",
        on_delete=models.CASCADE,
        related_name="email_sequences",
    )
    name = models.CharField(max_length=120)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT
    )
    exit_on_reply = models.BooleanField(default=True)
    exit_on_stage_change = models.BooleanField(default=True)
    exit_on_unsubscribe = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_sequences",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "name"],
                name="uniq_email_sequence_org_name",
            )
        ]

    def __str__(self):
        return self.name

    @property
    def can_edit(self):
        return self.status == self.Status.DRAFT


class SequenceStep(models.Model):
    sequence = models.ForeignKey(
        EmailSequence, on_delete=models.CASCADE, related_name="steps"
    )
    position = models.PositiveIntegerField()
    delay_days = models.PositiveIntegerField(
        default=0, help_text="Wait this many days after the previous step (or enrollment)."
    )
    delay_hours = models.PositiveIntegerField(
        default=0, help_text="Additional hours of delay (useful for testing)."
    )
    template = models.ForeignKey(
        EmailTemplate,
        on_delete=models.PROTECT,
        related_name="sequence_steps",
    )

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["sequence", "position"],
                name="uniq_sequence_step_position",
            )
        ]

    def __str__(self):
        return f"{self.sequence_id} step {self.position}"

    @property
    def delay_timedelta(self):
        from datetime import timedelta

        return timedelta(days=self.delay_days, hours=self.delay_hours)


class SequenceEnrollment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        EXITED = "exited", "Exited"
        CANCELLED = "cancelled", "Cancelled"

    class ExitReason(models.TextChoices):
        COMPLETED = "completed", "Completed"
        REPLY = "reply", "Reply"
        STAGE_CHANGE = "stage_change", "Stage change"
        UNSUBSCRIBE = "unsubscribe", "Unsubscribe"
        MANUAL = "manual", "Manual"
        CANCELLED = "cancelled", "Cancelled"

    sequence = models.ForeignKey(
        EmailSequence, on_delete=models.CASCADE, related_name="enrollments"
    )
    lead = models.ForeignKey(
        "leads.Lead",
        on_delete=models.CASCADE,
        related_name="sequence_enrollments",
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE
    )
    # Last completed step position; 0 means none sent yet.
    current_step_position = models.PositiveIntegerField(default=0)
    next_run_at = models.DateTimeField(null=True, blank=True, db_index=True)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    exit_reason = models.CharField(
        max_length=32, choices=ExitReason.choices, blank=True
    )
    enrolled_category_id = models.IntegerField(null=True, blank=True)
    reply_detected_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-enrolled_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["sequence", "lead"],
                name="uniq_sequence_lead_enrollment",
            )
        ]

    def __str__(self):
        return f"{self.sequence_id}:{self.lead_id} ({self.status})"


class SequenceStepSend(models.Model):
    enrollment = models.ForeignKey(
        SequenceEnrollment, on_delete=models.CASCADE, related_name="sends"
    )
    step = models.ForeignKey(
        SequenceStep, on_delete=models.CASCADE, related_name="sends"
    )
    outbound_email = models.ForeignKey(
        OutboundEmail,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sequence_sends",
    )
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sent_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "step"],
                name="uniq_enrollment_step_send",
            )
        ]

    def __str__(self):
        return f"enrollment {self.enrollment_id} step {self.step_id}"
