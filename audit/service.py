"""Append-only org audit log helpers."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from django.utils import timezone
from django.utils.dateparse import parse_date

from audit.models import AuditEntry


def log_event(
    *,
    organisation,
    action: str,
    summary: str,
    actor=None,
    object_type: str = AuditEntry.ObjectType.OTHER,
    object_id=None,
    object_repr: str = "",
    metadata: dict | None = None,
) -> AuditEntry | None:
    if organisation is None:
        return None
    return AuditEntry.objects.create(
        organisation=organisation,
        actor=actor if getattr(actor, "pk", None) else None,
        action=action[:64],
        object_type=object_type,
        object_id=object_id,
        object_repr=(object_repr or "")[:255],
        summary=summary[:500],
        metadata=metadata or {},
    )


def filter_entries(
    organisation,
    *,
    actor_id=None,
    object_type: str = "",
    date_from: str = "",
    date_to: str = "",
):
    qs = AuditEntry.objects.filter(organisation=organisation).select_related("actor")
    if actor_id:
        qs = qs.filter(actor_id=actor_id)
    if object_type:
        qs = qs.filter(object_type=object_type)
    if date_from:
        parsed = parse_date(date_from) if isinstance(date_from, str) else date_from
        if parsed:
            start = timezone.make_aware(
                datetime.combine(parsed, datetime.min.time())
            )
            qs = qs.filter(created_at__gte=start)
    if date_to:
        parsed = parse_date(date_to) if isinstance(date_to, str) else date_to
        if parsed:
            end = timezone.make_aware(
                datetime.combine(parsed, datetime.max.time())
            )
            qs = qs.filter(created_at__lte=end)
    return qs


def entries_to_csv(queryset) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "created_at",
            "actor",
            "action",
            "object_type",
            "object_id",
            "object_repr",
            "summary",
        ]
    )
    for entry in queryset.iterator():
        writer.writerow(
            [
                entry.created_at.isoformat(),
                entry.actor.username if entry.actor_id else "",
                entry.action,
                entry.object_type,
                entry.object_id or "",
                entry.object_repr,
                entry.summary,
            ]
        )
    return buffer.getvalue()


def log_lead_change(lead, *, action: str, summary: str, actor=None, **metadata):
    return log_event(
        organisation=lead.organisation,
        actor=actor,
        action=action,
        object_type=AuditEntry.ObjectType.LEAD,
        object_id=lead.pk,
        object_repr=f"{lead.first_name} {lead.last_name}".strip(),
        summary=summary,
        metadata=metadata,
    )


def log_campaign_change(campaign, *, action: str, summary: str, actor=None, **metadata):
    return log_event(
        organisation=campaign.organisation,
        actor=actor,
        action=action,
        object_type=AuditEntry.ObjectType.CAMPAIGN,
        object_id=campaign.pk,
        object_repr=campaign.name,
        summary=summary,
        metadata=metadata,
    )


def log_team_change(
    organisation,
    *,
    action: str,
    summary: str,
    actor=None,
    object_id=None,
    object_repr: str = "",
    **metadata,
):
    return log_event(
        organisation=organisation,
        actor=actor,
        action=action,
        object_type=AuditEntry.ObjectType.TEAM,
        object_id=object_id,
        object_repr=object_repr,
        summary=summary,
        metadata=metadata,
    )
