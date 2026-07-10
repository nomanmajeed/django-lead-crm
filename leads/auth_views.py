from django.contrib.auth.views import LoginView
from django.urls import reverse

from leads.permissions import user_can_manage_organisation, user_is_agent_member


class RoleBasedLoginView(LoginView):
    def get_success_url(self):
        user = self.request.user
        if user_can_manage_organisation(user):
            return reverse("app_home")
        if user_is_agent_member(user):
            return reverse("agent_home")
        return reverse("landing_page")
