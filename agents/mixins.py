from django.contrib.auth.mixins import AccessMixin
from django.shortcuts import redirect

from leads.permissions import user_can_manage_organisation


class OrganisorAndLoginRequiredMixin(AccessMixin):
    """Require authentication and an Owner/Admin membership."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not user_can_manage_organisation(
            request.user
        ):
            return redirect("leads:lead_list")
        return super().dispatch(request, *args, **kwargs)
