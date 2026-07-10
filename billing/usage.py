"""
Usage metering against plan caps.

Period logic
------------
Email usage is counted for the **current calendar month in UTC**
(``YYYY-MM-01 00:00:00+00:00`` → end of month). Counters reset automatically
at the start of each UTC month when queries use ``period_start()``.

Seat / lead / campaign / sequence counters are **point-in-time** (not period-
based): they reflect current rows for the organisation.

Soft warnings fire at ``SOFT_WARNING_RATIO`` (80%) of a finite cap.
Hard caps raise ``EntitlementDenied`` / block sends via ``assert_can_send_email``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone

from django.utils import timezone

from billing.entitlements import (
    PlanEntitlements,
    get_entitlements,
    require_within_limit,
)
from email_engine.models import Campaign, EmailSequence, OutboundEmail
from leads.models import Agent, Lead, Membership

SOFT_WARNING_RATIO = 0.8


def period_start(now=None) -> datetime:
    """First instant of the current UTC calendar month."""
    now = now or timezone.now()
    if timezone.is_aware(now):
        now = now.astimezone(dt_timezone.utc)
    else:
        now = timezone.make_aware(now, dt_timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def period_label(now=None) -> str:
    start = period_start(now)
    return start.strftime("%B %Y")


@dataclass
class UsageMeter:
    name: str
    label: str
    used: int
    limit: int | None
    soft_warning: bool
    hard_blocked: bool

    @property
    def remaining(self) -> int | None:
        if self.limit is None:
            return None
        return max(self.limit - self.used, 0)

    @property
    def ratio(self) -> float | None:
        if self.limit is None or self.limit == 0:
            return None
        return self.used / self.limit


def _meter(name: str, label: str, used: int, limit: int | None) -> UsageMeter:
    soft = False
    hard = False
    if limit is not None:
        hard = used >= limit
        soft = (not hard) and used >= int(limit * SOFT_WARNING_RATIO)
    return UsageMeter(
        name=name,
        label=label,
        used=used,
        limit=limit,
        soft_warning=soft,
        hard_blocked=hard,
    )


def emails_sent_this_period(organisation, *, now=None) -> int:
    if organisation is None:
        return 0
    return OutboundEmail.objects.filter(
        organisation=organisation,
        status=OutboundEmail.Status.SENT,
        sent_at__gte=period_start(now),
    ).count()


def usage_snapshot(organisation, *, now=None) -> dict:
    """
    Return meters + entitlements for billing UI.

    Keys: period_label, period_start, entitlements, meters (list), warnings (list).
    """
    entitlements = get_entitlements(organisation)
    now = now or timezone.now()
    seats = (
        Membership.objects.filter(organisation=organisation).count()
        if organisation
        else 0
    )
    leads = Lead.objects.for_org(organisation).count() if organisation else 0
    agents = Agent.objects.for_org(organisation).count() if organisation else 0
    campaigns = (
        Campaign.objects.filter(organisation=organisation).count()
        if organisation
        else 0
    )
    sequences = (
        EmailSequence.objects.filter(organisation=organisation).count()
        if organisation
        else 0
    )
    emails = emails_sent_this_period(organisation, now=now)

    meters = [
        _meter("seats", "Seats (members)", seats, entitlements.seats),
        _meter("agents", "Agents", agents, entitlements.seats),
        _meter("leads", "Leads", leads, entitlements.leads),
        _meter(
            "monthly_emails",
            f"Emails sent ({period_label(now)})",
            emails,
            entitlements.monthly_emails,
        ),
        _meter("campaigns", "Campaigns", campaigns, entitlements.campaigns),
        _meter("sequences", "Sequences", sequences, entitlements.sequences),
    ]
    warnings = [
        m
        for m in meters
        if m.soft_warning or m.hard_blocked
    ]
    return {
        "period_label": period_label(now),
        "period_start": period_start(now),
        "entitlements": entitlements,
        "meters": meters,
        "warnings": warnings,
        # Convenience flat map for templates
        "by_name": {m.name: m for m in meters},
    }


def assert_can_send_email(organisation) -> PlanEntitlements:
    """
    Hard-cap check for monthly emails. Raises EntitlementDenied when blocked.
    """
    used = emails_sent_this_period(organisation)
    return require_within_limit(organisation, "monthly_emails", used)


def assert_can_create_lead(organisation) -> PlanEntitlements:
    used = Lead.objects.for_org(organisation).count() if organisation else 0
    return require_within_limit(organisation, "leads", used)
