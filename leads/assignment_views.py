"""Organisation assignment settings (auto-assign / round-robin)."""

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View

from agents.mixins import OrganisorAndLoginRequiredMixin

from leads.assignment import active_agents_queryset


class AssignmentSettingsView(OrganisorAndLoginRequiredMixin, View):
    template_name = "app/assignment_settings.html"

    def get(self, request):
        organisation = request.organisation
        return render(
            request,
            self.template_name,
            {
                "topbar_title": "Assignment",
                "organisation": organisation,
                "agents": active_agents_queryset(organisation),
            },
        )

    def post(self, request):
        organisation = request.organisation
        organisation.auto_assign_enabled = request.POST.get("auto_assign_enabled") == "on"
        organisation.save(update_fields=["auto_assign_enabled", "updated_at"])
        if organisation.auto_assign_enabled:
            messages.success(
                request,
                "Auto-assign enabled. New unassigned leads will rotate across agents.",
            )
        else:
            messages.success(request, "Auto-assign disabled. Leads stay unassigned until manual assign.")
        return redirect("assignment_settings")
