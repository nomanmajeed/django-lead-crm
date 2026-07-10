"""Campaign and org-level email analytics from stored delivery events."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from email_engine.models import (
    Campaign,
    CampaignRecipient,
    EmailDeliveryEvent,
    OutboundEmail,
)


def _rate(numerator: int, denominator: int) -> float:
    if not denominator:
        return 0.0
    return round((numerator / denominator) * 100, 1)


def campaign_metrics(campaign: Campaign) -> dict:
    """
    Aggregate send/engagement metrics for a one-shot campaign.

    Rates use unique outbound emails that recorded the event type.
    """
    outbound_ids = list(
        campaign.recipients.exclude(outbound_email_id=None).values_list(
            "outbound_email_id", flat=True
        )
    )
    recipient_stats = {
        "recipients": campaign.recipients.count(),
        "sent_recipients": campaign.recipients.filter(
            status=CampaignRecipient.Status.SENT
        ).count(),
        "failed_recipients": campaign.recipients.filter(
            status=CampaignRecipient.Status.FAILED
        ).count(),
        "skipped_recipients": campaign.recipients.filter(
            status=CampaignRecipient.Status.SKIPPED
        ).count(),
    }

    if not outbound_ids:
        return {
            **recipient_stats,
            "sent": 0,
            "delivered": 0,
            "opens": 0,
            "unique_opens": 0,
            "clicks": 0,
            "unique_clicks": 0,
            "unsubscribes": 0,
            "bounces": 0,
            "open_rate": 0.0,
            "click_rate": 0.0,
            "unsubscribe_rate": 0.0,
            "bounce_rate": 0.0,
        }

    outbounds = OutboundEmail.objects.filter(pk__in=outbound_ids)
    sent = outbounds.filter(status=OutboundEmail.Status.SENT).count()

    events = EmailDeliveryEvent.objects.filter(outbound_email_id__in=outbound_ids)
    event_counts = events.values("event_type").annotate(c=Count("id"))
    by_type = {row["event_type"]: row["c"] for row in event_counts}

    unique_opens = (
        events.filter(event_type=EmailDeliveryEvent.EventType.OPEN)
        .values("outbound_email_id")
        .distinct()
        .count()
    )
    unique_clicks = (
        events.filter(event_type=EmailDeliveryEvent.EventType.CLICK)
        .values("outbound_email_id")
        .distinct()
        .count()
    )
    unique_unsubs = (
        events.filter(event_type=EmailDeliveryEvent.EventType.UNSUBSCRIBE)
        .values("outbound_email_id")
        .distinct()
        .count()
    )
    unique_bounces = (
        events.filter(event_type=EmailDeliveryEvent.EventType.BOUNCE)
        .values("outbound_email_id")
        .distinct()
        .count()
    )
    delivered_events = by_type.get(EmailDeliveryEvent.EventType.DELIVERED, 0)
    # Console/local providers often only emit SENT; treat sent as delivered baseline.
    delivered = delivered_events or sent

    return {
        **recipient_stats,
        "sent": sent,
        "delivered": delivered,
        "opens": by_type.get(EmailDeliveryEvent.EventType.OPEN, 0),
        "unique_opens": unique_opens,
        "clicks": by_type.get(EmailDeliveryEvent.EventType.CLICK, 0),
        "unique_clicks": unique_clicks,
        "unsubscribes": unique_unsubs,
        "bounces": unique_bounces,
        "open_rate": _rate(unique_opens, sent),
        "click_rate": _rate(unique_clicks, sent),
        "unsubscribe_rate": _rate(unique_unsubs, sent),
        "bounce_rate": _rate(unique_bounces, sent),
    }


def org_weekly_email_summary(organisation, *, days: int = 7) -> dict:
    """Org-scoped weekly send / engagement summary for the organiser dashboard."""
    if organisation is None:
        return {
            "days": days,
            "sent": 0,
            "opens": 0,
            "clicks": 0,
            "unsubscribes": 0,
            "bounces": 0,
            "open_rate": 0.0,
            "click_rate": 0.0,
            "campaigns_sent": 0,
        }

    since = timezone.now() - timedelta(days=days)
    outbounds = OutboundEmail.objects.filter(
        organisation=organisation,
        status=OutboundEmail.Status.SENT,
        sent_at__gte=since,
    )
    sent = outbounds.count()
    outbound_ids = list(outbounds.values_list("pk", flat=True))

    events = EmailDeliveryEvent.objects.filter(
        outbound_email_id__in=outbound_ids,
        created_at__gte=since,
    )
    unique_opens = (
        events.filter(event_type=EmailDeliveryEvent.EventType.OPEN)
        .values("outbound_email_id")
        .distinct()
        .count()
    )
    unique_clicks = (
        events.filter(event_type=EmailDeliveryEvent.EventType.CLICK)
        .values("outbound_email_id")
        .distinct()
        .count()
    )
    unsubs = (
        events.filter(event_type=EmailDeliveryEvent.EventType.UNSUBSCRIBE)
        .values("outbound_email_id")
        .distinct()
        .count()
    )
    bounces = (
        events.filter(event_type=EmailDeliveryEvent.EventType.BOUNCE)
        .values("outbound_email_id")
        .distinct()
        .count()
    )
    campaigns_sent = Campaign.objects.filter(
        organisation=organisation,
        status=Campaign.Status.SENT,
        completed_at__gte=since,
    ).count()

    return {
        "days": days,
        "sent": sent,
        "opens": unique_opens,
        "clicks": unique_clicks,
        "unsubscribes": unsubs,
        "bounces": bounces,
        "open_rate": _rate(unique_opens, sent),
        "click_rate": _rate(unique_clicks, sent),
        "campaigns_sent": campaigns_sent,
    }


def recent_campaign_reports(organisation, *, limit: int = 5) -> list[dict]:
    if organisation is None:
        return []
    campaigns = (
        Campaign.objects.filter(organisation=organisation)
        .exclude(status=Campaign.Status.DRAFT)
        .order_by("-updated_at")[:limit]
    )
    return [
        {"campaign": campaign, "metrics": campaign_metrics(campaign)}
        for campaign in campaigns
    ]
