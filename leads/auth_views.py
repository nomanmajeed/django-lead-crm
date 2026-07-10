from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.urls import reverse

from leads.permissions import user_can_manage_organisation, user_is_agent_member
from security.views import PENDING_2FA_SESSION_KEY


class RoleBasedLoginView(LoginView):
    def form_valid(self, form):
        user = form.get_user()
        if user.totp_enabled and user.totp_secret:
            self.request.session[PENDING_2FA_SESSION_KEY] = user.pk
            return redirect("two_factor_verify")
        return super().form_valid(form)

    def get_success_url(self):
        user = self.request.user
        if user_can_manage_organisation(user):
            return reverse("app_home")
        if user_is_agent_member(user):
            return reverse("agent_home")
        return reverse("landing_page")
