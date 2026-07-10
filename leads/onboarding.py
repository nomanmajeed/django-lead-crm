"""Onboarding checklist for new organisations."""

from __future__ import annotations

from dataclasses import dataclass

from email_engine.models import Campaign
from leads.models import Invite, Lead, Membership


@dataclass(frozen=True)
class OnboardingItem:
    key: str
    label: str
    description: str
    url_name: str
    done: bool


def _invite_teammate_done(organisation) -> bool:
    if organisation is None:
        return False
    if (
        Membership.objects.filter(organisation=organisation)
        .exclude(role=Membership.Role.OWNER)
        .exists()
    ):
        return True
    return Invite.objects.filter(
        organisation=organisation, accepted_at__isnull=False
    ).exists()


def _import_leads_done(organisation) -> bool:
    if organisation is None:
        return False
    return Lead.objects.for_org(organisation).exists()


def _first_campaign_done(organisation) -> bool:
    if organisation is None:
        return False
    return Campaign.objects.filter(
        organisation=organisation,
        status=Campaign.Status.SENT,
    ).exists()


def onboarding_items(organisation) -> list[OnboardingItem]:
    return [
        OnboardingItem(
            key="invite",
            label="Invite a teammate",
            description="Add an agent or admin so work can be shared.",
            url_name="team",
            done=_invite_teammate_done(organisation),
        ),
        OnboardingItem(
            key="import",
            label="Import leads",
            description="Bring contacts into your pipeline from CSV.",
            url_name="leads:lead_import",
            done=_import_leads_done(organisation),
        ),
        OnboardingItem(
            key="campaign",
            label="Send your first campaign",
            description="Deliver a one-shot email to a contact list.",
            url_name="campaign_index",
            done=_first_campaign_done(organisation),
        ),
    ]


def onboarding_snapshot(organisation) -> dict:
    if organisation is None:
        return {"show": False, "items": [], "completed": 0, "total": 0, "all_done": True}
    if organisation.onboarding_dismissed_at is not None:
        return {"show": False, "items": [], "completed": 0, "total": 0, "all_done": True}
    items = onboarding_items(organisation)
    completed = sum(1 for item in items if item.done)
    total = len(items)
    return {
        "show": True,
        "items": items,
        "completed": completed,
        "total": total,
        "all_done": completed == total,
    }
