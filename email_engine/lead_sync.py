"""Sync outbound email events onto lead timeline + last_emailed_at."""

from __future__ import annotations

from django.utils import timezone

from leads.models import Lead, LeadActivity, record_lead_activity


def resolve_lead_for_outbound(outbound) -> Lead | None:
    """Find the org-scoped lead for an outbound email, if any."""
    if outbound is None:
        return None

    # Prefer explicit campaign / sequence linkage
    recipient = (
        outbound.campaign_recipients.select_related("lead").first()
        if hasattr(outbound, "campaign_recipients")
        else None
    )
    if recipient is not None:
        return recipient.lead

    seq_send = (
        outbound.sequence_sends.select_related("enrollment__lead").first()
        if hasattr(outbound, "sequence_sends")
        else None
    )
    if seq_send is not None:
        return seq_send.enrollment.lead

    org = outbound.organisation
    email = (outbound.to_email or "").strip()
    if org is None or not email:
        return None
    return (
        Lead.objects.for_org(org)
        .filter(email__iexact=email)
        .order_by("pk")
        .first()
    )


def touch_last_emailed(lead: Lead, when=None) -> None:
    when = when or timezone.now()
    Lead.objects.filter(pk=lead.pk).update(last_emailed_at=when)
    lead.last_emailed_at = when


def sync_email_sent(outbound, *, lead: Lead | None = None) -> LeadActivity | None:
    lead = lead or resolve_lead_for_outbound(outbound)
    if lead is None:
        return None
    touch_last_emailed(lead, outbound.sent_at or timezone.now())
    subject = (outbound.subject or "Email")[:80]
    return record_lead_activity(
        lead,
        kind=LeadActivity.Kind.EMAIL_SENT,
        summary=f"Email sent: {subject}",
    )


def sync_email_open(outbound) -> LeadActivity | None:
    lead = resolve_lead_for_outbound(outbound)
    if lead is None:
        return None
    subject = (outbound.subject or "Email")[:80]
    return record_lead_activity(
        lead,
        kind=LeadActivity.Kind.EMAIL_OPEN,
        summary=f"Opened email: {subject}",
    )


def sync_email_click(outbound, *, url: str = "") -> LeadActivity | None:
    lead = resolve_lead_for_outbound(outbound)
    if lead is None:
        return None
    subject = (outbound.subject or "Email")[:60]
    suffix = f" → {url[:80]}" if url else ""
    return record_lead_activity(
        lead,
        kind=LeadActivity.Kind.EMAIL_CLICK,
        summary=f"Clicked email: {subject}{suffix}"[:255],
    )


def sync_email_unsubscribe(outbound) -> LeadActivity | None:
    lead = resolve_lead_for_outbound(outbound)
    if lead is None:
        return None
    return record_lead_activity(
        lead,
        kind=LeadActivity.Kind.EMAIL_UNSUBSCRIBE,
        summary=f"Unsubscribed ({outbound.to_email})",
    )


def lead_email_history(lead: Lead, *, limit: int = 25) -> list[dict]:
    """Campaign + sequence sends for the lead detail panel (org-scoped via lead)."""
    from email_engine.models import CampaignRecipient, SequenceStepSend

    rows: list[dict] = []
    for recipient in (
        CampaignRecipient.objects.filter(lead=lead)
        .select_related("campaign", "outbound_email")
        .order_by("-updated_at")[:limit]
    ):
        rows.append(
            {
                "kind": "campaign",
                "label": recipient.campaign.name,
                "status": recipient.get_status_display(),
                "subject": (
                    recipient.outbound_email.subject
                    if recipient.outbound_email
                    else ""
                ),
                "at": recipient.updated_at,
                "outbound": recipient.outbound_email,
            }
        )
    for send in (
        SequenceStepSend.objects.filter(enrollment__lead=lead)
        .select_related(
            "enrollment__sequence", "step", "outbound_email"
        )
        .order_by("-sent_at")[:limit]
    ):
        rows.append(
            {
                "kind": "sequence",
                "label": (
                    f"{send.enrollment.sequence.name} · step {send.step.position}"
                ),
                "status": "Sent",
                "subject": send.outbound_email.subject if send.outbound_email else "",
                "at": send.sent_at,
                "outbound": send.outbound_email,
            }
        )
    rows.sort(key=lambda r: r["at"] or timezone.now(), reverse=True)
    return rows[:limit]
