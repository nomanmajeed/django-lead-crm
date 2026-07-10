"""Manual and round-robin lead assignment helpers."""

from django.db import transaction

from leads.models import Agent, LeadActivity, Organisation, record_lead_activity


def active_agents_queryset(organisation):
    return (
        Agent.objects.for_org(organisation)
        .select_related("user")
        .order_by("id")
    )


@transaction.atomic
def next_round_robin_agent(organisation):
    """
    Pick the next agent for this org and advance the cursor.

    Locks the organisation row so concurrent creates distribute fairly.
    """
    org = Organisation.objects.select_for_update().get(pk=organisation.pk)
    agents = list(active_agents_queryset(org))
    if not agents:
        return None
    index = org.round_robin_cursor % len(agents)
    agent = agents[index]
    org.round_robin_cursor = (index + 1) % len(agents)
    org.save(update_fields=["round_robin_cursor", "updated_at"])
    return agent


def maybe_auto_assign(lead, *, actor=None):
    """Assign an unassigned lead when org auto-assign is enabled."""
    if lead.agent_id:
        return lead
    organisation = lead.organisation
    if not organisation.auto_assign_enabled:
        return lead
    agent = next_round_robin_agent(organisation)
    if agent is None:
        return lead
    lead.agent = agent
    lead.save(update_fields=["agent"])
    record_lead_activity(
        lead,
        kind=LeadActivity.Kind.ASSIGNMENT,
        summary=f"Auto-assigned to {agent.user.username} (round-robin)",
        actor=actor,
    )
    from notifications.service import notify_assignment

    notify_assignment(lead, agent, actor=actor)
    from audit.service import log_lead_change

    log_lead_change(
        lead,
        action="lead.assigned",
        summary=f"Auto-assigned to {agent.user.username}",
        actor=actor,
        agent_id=agent.pk,
        auto=True,
    )
    return lead


def assign_lead_to_agent(lead, agent, *, actor=None):
    """Manual assignment override."""
    lead.agent = agent
    lead.save(update_fields=["agent"])
    record_lead_activity(
        lead,
        kind=LeadActivity.Kind.ASSIGNMENT,
        summary=f"Assigned to {agent.user.username}",
        actor=actor,
    )
    from notifications.service import notify_assignment

    notify_assignment(lead, agent, actor=actor)
    from audit.service import log_lead_change

    log_lead_change(
        lead,
        action="lead.assigned",
        summary=f"Assigned to {agent.user.username}",
        actor=actor,
        agent_id=agent.pk,
    )
    return lead
