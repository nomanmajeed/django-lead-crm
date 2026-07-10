"""djcrm URL Configuration"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import (
    LogoutView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.urls import include, path
from django.views.generic import RedirectView, TemplateView

from leads.assignment_views import AssignmentSettingsView
from leads.auth_views import RoleBasedLoginView
from leads.invites import (
    InviteAcceptView,
    TeamInviteCreateView,
    TeamInviteListView,
    TeamInviteResendView,
    TeamInviteRevokeView,
)
from leads.views import AgentHomeView, AppHomeView, SignupView, landing_page
from email_engine.webhooks import email_webhook

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", landing_page, name="landing_page"),
    # Organiser app space
    path("app/", AppHomeView.as_view(), name="app_home"),
    path("app/leads/", include(("leads.urls", "leads"), namespace="leads")),
    path("app/agents/", include(("agents.urls", "agents"), namespace="agents")),
    path("app/team/", TeamInviteListView.as_view(), name="team"),
    path(
        "app/team/invites/create/",
        TeamInviteCreateView.as_view(),
        name="team_invite_create",
    ),
    path(
        "app/team/invites/<int:pk>/revoke/",
        TeamInviteRevokeView.as_view(),
        name="team_invite_revoke",
    ),
    path(
        "app/team/invites/<int:pk>/resend/",
        TeamInviteResendView.as_view(),
        name="team_invite_resend",
    ),
    path(
        "app/settings/assignment/",
        AssignmentSettingsView.as_view(),
        name="assignment_settings",
    ),
    # Agent workspace
    path("agent/", AgentHomeView.as_view(), name="agent_home"),
    path(
        "agent/leads/",
        include(("leads.agent_urls", "agent_leads"), namespace="agent_leads"),
    ),
    # Public invite accept
    path(
        "invites/<str:token>/",
        InviteAcceptView.as_view(),
        name="invite_accept",
    ),
    # Legacy redirects
    path(
        "leads/",
        RedirectView.as_view(pattern_name="leads:lead_list", permanent=False),
    ),
    path(
        "agents/",
        RedirectView.as_view(pattern_name="agents:agent_list", permanent=False),
    ),
    path("signup/", SignupView.as_view(), name="signup"),
    path("login/", RoleBasedLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("reset-password/", PasswordResetView.as_view(), name="reset-password"),
    path(
        "password-reset-done/",
        PasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "password-reset-confirm/<uidb64>/<token>/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password-reset-complete/",
        PasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
    path(
        "ui/marketing/",
        TemplateView.as_view(template_name="ui/marketing_sample.html"),
        name="ui_marketing",
    ),
    path(
        "ui/app/",
        RedirectView.as_view(pattern_name="app_home", permanent=False),
        name="ui_app",
    ),
    path(
        "ui/agent/",
        RedirectView.as_view(pattern_name="agent_home", permanent=False),
        name="ui_agent",
    ),
    path(
        "webhooks/email/<str:provider>/",
        email_webhook,
        name="email_webhook",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
