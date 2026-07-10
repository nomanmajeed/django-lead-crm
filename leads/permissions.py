"""Membership-based permission helpers. Membership is the source of truth."""

from leads.models import Membership, Organisation

MANAGEMENT_ROLES = {
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
}


def get_user_organisation(user):
    """Resolve the primary organisation for a user via membership (or legacy links)."""
    if not getattr(user, "is_authenticated", False):
        return None

    membership = (
        user.memberships.select_related("organisation")
        .order_by("created_at")
        .first()
    )
    if membership:
        return membership.organisation

    try:
        return user.owned_organisation
    except Organisation.DoesNotExist:
        pass

    agent = getattr(user, "agent", None)
    if agent is not None:
        return agent.organisation

    return None


def user_has_role(user, organisation, roles):
    if not getattr(user, "is_authenticated", False) or organisation is None:
        return False
    return user.memberships.filter(
        organisation=organisation,
        role__in=roles,
    ).exists()


def user_can_manage_organisation(user, organisation=None):
    """Owner/Admin can manage team-scoped resources."""
    if not getattr(user, "is_authenticated", False):
        return False

    qs = user.memberships.filter(role__in=MANAGEMENT_ROLES)
    if organisation is not None:
        qs = qs.filter(organisation=organisation)
    return qs.exists()


def user_is_agent_member(user, organisation=None):
    if not getattr(user, "is_authenticated", False):
        return False

    qs = user.memberships.filter(role=Membership.Role.AGENT)
    if organisation is not None:
        qs = qs.filter(organisation=organisation)
    return qs.exists()
