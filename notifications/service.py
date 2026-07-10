"""Create org- and user-scoped in-app notifications (optional email)."""

from __future__ import annotations

from django.urls import reverse
from django.utils import timezone

from leads.models import Membership
from notifications.models import Notification


def notify_user(
    *,
    organisation,
    recipient,
    kind: str,
    title: str,
    body: str = "",
    link_url: str = "",
    send_email: bool = False,
) -> Notification | None:
    if organisation is None or recipient is None:
        return None
    notification = Notification.objects.create(
        organisation=organisation,
        recipient=recipient,
        kind=kind,
        title=title[:200],
        body=body,
        link_url=link_url[:500],
    )
    if send_email and getattr(recipient, "email", None):
        from email_engine.service import queue_transactional_email

        queue_transactional_email(
            to_email=recipient.email,
            subject=title[:255],
            body_text=body or title,
            body_html=f"<p>{body or title}</p>",
            organisation=organisation,
            track=False,
            enforce_quota=False,
        )
    return notification


def notify_org_managers(
    organisation,
    *,
    kind: str,
    title: str,
    body: str = "",
    link_url: str = "",
    exclude_user=None,
):
    if organisation is None:
        return []
    qs = Membership.objects.filter(
        organisation=organisation,
        role__in={
            Membership.Role.OWNER,
            Membership.Role.ADMIN,
        },
    ).select_related("user")
    created = []
    for membership in qs:
        if exclude_user and membership.user_id == getattr(exclude_user, "pk", None):
            continue
        note = notify_user(
            organisation=organisation,
            recipient=membership.user,
            kind=kind,
            title=title,
            body=body,
            link_url=link_url,
        )
        if note:
            created.append(note)
    return created


def mark_read(notification: Notification) -> Notification:
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])
    return notification


def mark_all_read(organisation, user) -> int:
    return Notification.objects.filter(
        organisation=organisation,
        recipient=user,
        read_at__isnull=True,
    ).update(read_at=timezone.now())


def notify_assignment(lead, agent, *, actor=None):
    if agent is None or agent.user_id is None:
        return None
    link = reverse("agent_leads:lead_detail", kwargs={"pk": lead.pk})
    return notify_user(
        organisation=lead.organisation,
        recipient=agent.user,
        kind=Notification.Kind.ASSIGNMENT,
        title=f"New lead assigned: {lead.first_name} {lead.last_name}",
        body=(
            f"You were assigned {lead.first_name} {lead.last_name}"
            + (f" by {actor.username}" if actor else "")
            + "."
        ),
        link_url=link,
    )


def notify_campaign_finished(campaign):
    link = reverse("campaign_report", kwargs={"pk": campaign.pk})
    title = f"Campaign finished: {campaign.name}"
    body = f"“{campaign.name}” finished sending."
    notes = notify_org_managers(
        campaign.organisation,
        kind=Notification.Kind.CAMPAIGN,
        title=title,
        body=body,
        link_url=link,
    )
    if campaign.created_by_id:
        already = {n.recipient_id for n in notes}
        if campaign.created_by_id not in already:
            note = notify_user(
                organisation=campaign.organisation,
                recipient=campaign.created_by,
                kind=Notification.Kind.CAMPAIGN,
                title=title,
                body=body,
                link_url=link,
            )
            if note:
                notes.append(note)
    return notes


def notify_invite_accepted(invite, user):
    link = reverse("team")
    title = f"Invite accepted: {user.email or user.username}"
    body = f"{user.username} joined as {invite.get_role_display()}."
    notes = []
    if invite.invited_by_id:
        note = notify_user(
            organisation=invite.organisation,
            recipient=invite.invited_by,
            kind=Notification.Kind.INVITE,
            title=title,
            body=body,
            link_url=link,
        )
        if note:
            notes.append(note)
    notes.extend(
        notify_org_managers(
            invite.organisation,
            kind=Notification.Kind.INVITE,
            title=title,
            body=body,
            link_url=link,
            exclude_user=invite.invited_by,
        )
    )
    return notes


def notify_billing_change(organisation, *, plan: str, actor_label: str = "Billing"):
    link = reverse("billing_plans")
    return notify_org_managers(
        organisation,
        kind=Notification.Kind.BILLING,
        title=f"Plan updated to {plan.title()}",
        body=f"{actor_label}: organisation plan is now {plan}.",
        link_url=link,
    )
