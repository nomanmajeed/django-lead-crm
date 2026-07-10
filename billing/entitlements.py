"""
Plan entitlements: limits and feature flags keyed by Organisation.plan.

Reusable from views and tasks. Stripe (ticket 27) will change the plan value;
this module stays the source of truth for what each plan allows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from leads.models import Organisation


@dataclass(frozen=True)
class PlanEntitlements:
    key: str
    label: str
    seats: int | None
    leads: int | None
    monthly_emails: int | None
    campaigns: int | None
    sequences: int | None
    features: dict[str, bool]

    def has_feature(self, feature: str) -> bool:
        return bool(self.features.get(feature, False))

    def limit(self, name: str) -> int | None:
        return getattr(self, name, None)

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "seats": self.seats,
            "leads": self.leads,
            "monthly_emails": self.monthly_emails,
            "campaigns": self.campaigns,
            "sequences": self.sequences,
            "features": dict(self.features),
        }


# None = unlimited
PLAN_CATALOG: dict[str, PlanEntitlements] = {
    Organisation.Plan.FREE: PlanEntitlements(
        key=Organisation.Plan.FREE,
        label="Free",
        seats=2,
        leads=100,
        monthly_emails=200,
        campaigns=5,
        sequences=0,
        features={
            "campaigns": True,
            "sequences": False,
            "analytics": False,
            "assignment_rules": True,
        },
    ),
    Organisation.Plan.PRO: PlanEntitlements(
        key=Organisation.Plan.PRO,
        label="Pro",
        seats=10,
        leads=5_000,
        monthly_emails=10_000,
        campaigns=50,
        sequences=20,
        features={
            "campaigns": True,
            "sequences": True,
            "analytics": True,
            "assignment_rules": True,
        },
    ),
    Organisation.Plan.BUSINESS: PlanEntitlements(
        key=Organisation.Plan.BUSINESS,
        label="Business",
        seats=None,
        leads=None,
        monthly_emails=None,
        campaigns=None,
        sequences=None,
        features={
            "campaigns": True,
            "sequences": True,
            "analytics": True,
            "assignment_rules": True,
        },
    ),
}


class EntitlementDenied(Exception):
    """Raised when a plan feature or limit blocks an action."""

    def __init__(self, message: str, *, feature: str = "", upgrade_required: bool = True):
        super().__init__(message)
        self.message = message
        self.feature = feature
        self.upgrade_required = upgrade_required


def get_entitlements(organisation) -> PlanEntitlements:
    """Return entitlements for an org plan (defaults to Free)."""
    if organisation is None:
        return PLAN_CATALOG[Organisation.Plan.FREE]
    plan = organisation.plan or Organisation.Plan.FREE
    return PLAN_CATALOG.get(plan, PLAN_CATALOG[Organisation.Plan.FREE])


def has_feature(organisation, feature: str) -> bool:
    return get_entitlements(organisation).has_feature(feature)


def require_feature(organisation, feature: str) -> PlanEntitlements:
    """Return entitlements or raise EntitlementDenied with an upgrade message."""
    entitlements = get_entitlements(organisation)
    if not entitlements.has_feature(feature):
        raise EntitlementDenied(
            f"{feature.replace('_', ' ').title()} is not available on the "
            f"{entitlements.label} plan. Upgrade to Pro or Business to unlock it.",
            feature=feature,
            upgrade_required=True,
        )
    return entitlements


def within_limit(organisation, limit_name: str, current: int) -> bool:
    """True if current usage is under the plan cap (unlimited caps always pass)."""
    cap = get_entitlements(organisation).limit(limit_name)
    if cap is None:
        return True
    return current < cap


def require_within_limit(organisation, limit_name: str, current: int) -> PlanEntitlements:
    entitlements = get_entitlements(organisation)
    cap = entitlements.limit(limit_name)
    if cap is not None and current >= cap:
        raise EntitlementDenied(
            f"Your {entitlements.label} plan allows {cap} {limit_name.replace('_', ' ')}. "
            f"Upgrade to increase this limit.",
            feature=limit_name,
            upgrade_required=True,
        )
    return entitlements


def all_plans() -> list[PlanEntitlements]:
    return [
        PLAN_CATALOG[Organisation.Plan.FREE],
        PLAN_CATALOG[Organisation.Plan.PRO],
        PLAN_CATALOG[Organisation.Plan.BUSINESS],
    ]
