from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.shortcuts import render
from django.views import View

from agents.mixins import OrganisorAndLoginRequiredMixin
from audit.models import AuditEntry
from audit.service import entries_to_csv, filter_entries
from billing.entitlements import has_feature
from billing.gates import feature_or_upgrade
from leads.models import Membership

User = get_user_model()


class AuditLogView(OrganisorAndLoginRequiredMixin, View):
    def get(self, request):
        org = request.organisation
        actor_id = request.GET.get("actor") or ""
        object_type = request.GET.get("object_type") or ""
        date_from = request.GET.get("date_from") or ""
        date_to = request.GET.get("date_to") or ""

        entries = filter_entries(
            org,
            actor_id=actor_id or None,
            object_type=object_type,
            date_from=date_from,
            date_to=date_to,
        )[:200]

        actors = (
            User.objects.filter(
                memberships__organisation=org,
                memberships__role__in={
                    Membership.Role.OWNER,
                    Membership.Role.ADMIN,
                    Membership.Role.AGENT,
                },
            )
            .distinct()
            .order_by("username")
        )

        return render(
            request,
            "app/audit/log.html",
            {
                "topbar_title": "Audit log",
                "entries": entries,
                "actors": actors,
                "object_types": AuditEntry.ObjectType.choices,
                "filters": {
                    "actor": actor_id,
                    "object_type": object_type,
                    "date_from": date_from,
                    "date_to": date_to,
                },
                "can_export": has_feature(org, "audit_export"),
            },
        )


class AuditExportView(OrganisorAndLoginRequiredMixin, View):
    def get(self, request):
        blocked = feature_or_upgrade(request, "audit_export")
        if blocked is not None:
            return blocked

        org = request.organisation
        entries = filter_entries(
            org,
            actor_id=request.GET.get("actor") or None,
            object_type=request.GET.get("object_type") or "",
            date_from=request.GET.get("date_from") or "",
            date_to=request.GET.get("date_to") or "",
        )
        csv_body = entries_to_csv(entries)
        response = HttpResponse(csv_body, content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="audit-log.csv"'
        )
        return response
