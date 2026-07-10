from django.contrib.auth.mixins import AccessMixin
from django.shortcuts import redirect

from leads.permissions import (
    user_can_manage_organisation,
    user_is_agent_member,
    user_is_org_owner,
)


class OrganisorAndLoginRequiredMixin(AccessMixin):
    """Require authentication and an Owner/Admin membership."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not user_can_manage_organisation(request.user):
            if user_is_agent_member(request.user):
                return redirect("agent_home")
            return redirect("landing_page")
        return super().dispatch(request, *args, **kwargs)


class OwnerRequiredMixin(OrganisorAndLoginRequiredMixin):
    """Require the Owner role for the current organisation."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not user_can_manage_organisation(request.user):
            if user_is_agent_member(request.user):
                return redirect("agent_home")
            return redirect("landing_page")
        if not user_is_org_owner(request.user, getattr(request, "organisation", None)):
            return redirect("settings_hub")
        return super(OrganisorAndLoginRequiredMixin, self).dispatch(
            request, *args, **kwargs
        )
