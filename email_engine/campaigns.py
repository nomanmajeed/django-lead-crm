"""One-shot campaign enqueue, cancel, and batch send helpers."""

from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from email_engine.merge import build_merge_context, render_merge
from email_engine.models import Campaign, CampaignRecipient, OutboundEmail
from email_engine.service import queue_transactional_email
from leads.lists import resolve_list_members


def recipient_counts(campaign: Campaign) -> dict:
    qs = campaign.recipients.all()
    return {
        "total": qs.count(),
        "pending": qs.filter(status=CampaignRecipient.Status.PENDING).count(),
        "queued": qs.filter(status=CampaignRecipient.Status.QUEUED).count(),
        "sent": qs.filter(status=CampaignRecipient.Status.SENT).count(),
        "failed": qs.filter(status=CampaignRecipient.Status.FAILED).count(),
        "skipped": qs.filter(status=CampaignRecipient.Status.SKIPPED).count(),
    }


def materialize_recipients(campaign: Campaign) -> int:
    """Create pending recipient rows from the campaign list/segment."""
    if campaign.recipients.exists():
        return campaign.recipients.count()

    leads = resolve_list_members(campaign.contact_list).exclude(email="")
    rows = [
        CampaignRecipient(
            campaign=campaign,
            lead=lead,
            status=CampaignRecipient.Status.PENDING,
        )
        for lead in leads.iterator()
    ]
    if rows:
        CampaignRecipient.objects.bulk_create(rows, ignore_conflicts=True)
    return campaign.recipients.count()


def cancel_campaign(campaign: Campaign) -> Campaign:
    if not campaign.can_cancel and campaign.status != Campaign.Status.DRAFT:
        return campaign
    campaign.status = Campaign.Status.CANCELLED
    campaign.completed_at = timezone.now()
    campaign.save(update_fields=["status", "completed_at", "updated_at"])
    campaign.recipients.filter(status=CampaignRecipient.Status.PENDING).update(
        status=CampaignRecipient.Status.SKIPPED,
        error_message="Campaign cancelled",
        updated_at=timezone.now(),
    )
    return campaign


def schedule_or_send_campaign(
    campaign: Campaign,
    *,
    send_now: bool = True,
    scheduled_at=None,
) -> Campaign:
    """
    Materialize recipients and either send immediately or schedule for later.
    """
    if campaign.status not in {
        Campaign.Status.DRAFT,
        Campaign.Status.SCHEDULED,
    }:
        raise ValueError("Campaign cannot be started from its current status.")

    count = materialize_recipients(campaign)
    if count == 0:
        raise ValueError("No recipients with email addresses on this list.")

    from email_engine.tasks import process_campaign_batch_task

    def _enqueue(send_immediately: bool, eta=None):
        # TestCase wraps tests in a transaction; on_commit never fires there.
        # Eager mode should run inline so local/dev and tests stay deterministic.
        if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
            process_campaign_batch_task.delay(campaign.pk)
            return
        if send_immediately:
            transaction.on_commit(
                lambda: process_campaign_batch_task.delay(campaign.pk)
            )
        else:
            transaction.on_commit(
                lambda: process_campaign_batch_task.apply_async(
                    args=[campaign.pk], eta=eta
                )
            )

    if send_now or scheduled_at is None:
        campaign.status = Campaign.Status.SENDING
        campaign.scheduled_at = None
        campaign.started_at = timezone.now()
        campaign.completed_at = None
        campaign.save(
            update_fields=[
                "status",
                "scheduled_at",
                "started_at",
                "completed_at",
                "updated_at",
            ]
        )
        _enqueue(send_immediately=True)
        return campaign

    campaign.status = Campaign.Status.SCHEDULED
    campaign.scheduled_at = scheduled_at
    campaign.started_at = None
    campaign.completed_at = None
    campaign.save(
        update_fields=[
            "status",
            "scheduled_at",
            "started_at",
            "completed_at",
            "updated_at",
        ]
    )
    _enqueue(send_immediately=False, eta=scheduled_at)
    return campaign


def _send_one_recipient(recipient: CampaignRecipient) -> CampaignRecipient:
    campaign = recipient.campaign
    lead = recipient.lead
    to_email = (lead.email or "").strip()
    if not to_email:
        recipient.status = CampaignRecipient.Status.SKIPPED
        recipient.error_message = "Lead has no email"
        recipient.save(
            update_fields=["status", "error_message", "updated_at"]
        )
        return recipient

    from email_engine.sequences import is_email_suppressed

    if is_email_suppressed(campaign.organisation, to_email):
        recipient.status = CampaignRecipient.Status.SKIPPED
        recipient.error_message = "Address suppressed"
        recipient.save(
            update_fields=["status", "error_message", "updated_at"]
        )
        return recipient

    context = build_merge_context(
        lead=lead, organisation=campaign.organisation
    )
    template = campaign.template
    outbound = queue_transactional_email(
        to_email=to_email,
        subject=render_merge(template.subject, context),
        body_text=render_merge(
            template.body_text or template.body_html, context
        ),
        body_html=render_merge(template.body_html, context),
        organisation=campaign.organisation,
        track=True,
        respect_suppression=True,
    )
    recipient.outbound_email = outbound
    if outbound.status == OutboundEmail.Status.SUPPRESSED:
        recipient.status = CampaignRecipient.Status.SKIPPED
        recipient.error_message = "Address suppressed"
    elif outbound.status == OutboundEmail.Status.QUOTA_EXCEEDED:
        recipient.status = CampaignRecipient.Status.SKIPPED
        recipient.error_message = outbound.error_message or "Monthly email quota exceeded"
    elif outbound.status == OutboundEmail.Status.SENT:
        recipient.status = CampaignRecipient.Status.SENT
        recipient.error_message = ""
    elif outbound.status == OutboundEmail.Status.QUEUED:
        recipient.status = CampaignRecipient.Status.QUEUED
        recipient.error_message = ""
    else:
        recipient.status = CampaignRecipient.Status.FAILED
        recipient.error_message = outbound.error_message or "Send failed"
    recipient.save(
        update_fields=[
            "outbound_email",
            "status",
            "error_message",
            "updated_at",
        ]
    )
    return recipient


def process_campaign_batch(campaign_id: int, *, chain: bool = True) -> str:
    """
    Send up to batch_size pending recipients, then re-queue or finish.

    Returns a short status string for Celery result / tests.
    Set chain=False to process a single batch without enqueueing the next
    (useful for tests that assert cancel between batches).
    """
    try:
        campaign = Campaign.objects.select_related(
            "template", "organisation", "contact_list"
        ).get(pk=campaign_id)
    except Campaign.DoesNotExist:
        return "missing"

    campaign.refresh_from_db()
    if campaign.status == Campaign.Status.CANCELLED:
        campaign.recipients.filter(
            status=CampaignRecipient.Status.PENDING
        ).update(
            status=CampaignRecipient.Status.SKIPPED,
            error_message="Campaign cancelled",
            updated_at=timezone.now(),
        )
        return "cancelled"

    if campaign.status == Campaign.Status.SCHEDULED:
        # ETA fired — move into sending
        campaign.status = Campaign.Status.SENDING
        campaign.started_at = timezone.now()
        campaign.save(update_fields=["status", "started_at", "updated_at"])

    if campaign.status != Campaign.Status.SENDING:
        return campaign.status

    batch_size = campaign.batch_size or getattr(
        settings, "CAMPAIGN_BATCH_SIZE", 25
    )
    pending = list(
        campaign.recipients.filter(status=CampaignRecipient.Status.PENDING)
        .select_related("lead")
        .order_by("pk")[:batch_size]
    )

    if not pending:
        _finalize_if_done(campaign)
        return campaign.status

    for recipient in pending:
        campaign.refresh_from_db(fields=["status"])
        if campaign.status == Campaign.Status.CANCELLED:
            campaign.recipients.filter(
                status=CampaignRecipient.Status.PENDING
            ).update(
                status=CampaignRecipient.Status.SKIPPED,
                error_message="Campaign cancelled",
                updated_at=timezone.now(),
            )
            return "cancelled"
        try:
            _send_one_recipient(recipient)
        except Exception as exc:  # noqa: BLE001 — isolate per-recipient failures
            recipient.status = CampaignRecipient.Status.FAILED
            recipient.error_message = str(exc)[:500]
            recipient.save(
                update_fields=["status", "error_message", "updated_at"]
            )

    campaign.refresh_from_db()
    if campaign.status == Campaign.Status.CANCELLED:
        return "cancelled"

    remaining = campaign.recipients.filter(
        status=CampaignRecipient.Status.PENDING
    ).exists()
    if remaining:
        if not chain:
            return "batch_queued"
        from email_engine.tasks import process_campaign_batch_task

        delay = campaign.batch_delay_seconds
        if delay is None:
            delay = getattr(settings, "CAMPAIGN_BATCH_DELAY_SECONDS", 1)
        if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False) or delay <= 0:
            process_campaign_batch_task.delay(campaign.pk)
        else:
            process_campaign_batch_task.apply_async(
                args=[campaign.pk], countdown=delay
            )
        return "batch_queued"

    _finalize_if_done(campaign)
    return campaign.status


def _finalize_if_done(campaign: Campaign) -> None:
    if campaign.recipients.filter(
        status=CampaignRecipient.Status.PENDING
    ).exists():
        return
    if campaign.status == Campaign.Status.CANCELLED:
        return
    already_done = campaign.status == Campaign.Status.SENT
    campaign.status = Campaign.Status.SENT
    campaign.completed_at = timezone.now()
    campaign.save(update_fields=["status", "completed_at", "updated_at"])
    if not already_done:
        from notifications.service import notify_campaign_finished

        notify_campaign_finished(campaign)
