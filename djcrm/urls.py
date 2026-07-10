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

from audit.views import AuditExportView, AuditLogView
from notifications.views import NotificationInboxView
from billing.views import BillingPlansView, BillingUsageView
from billing.webhooks import stripe_webhook
from email_engine.campaign_views import (
    CampaignCreateView,
    CampaignDetailView,
    CampaignIndexView,
    CampaignReportView,
)
from email_engine.compliance_views import ComplianceSettingsView
from email_engine.sequence_views import (
    SequenceCreateView,
    SequenceDetailView,
    SequenceIndexView,
)
from email_engine.template_views import (
    EmailTemplateCreateView,
    EmailTemplateDetailView,
    EmailTemplateIndexView,
)
from email_engine.tracking_views import track_click, track_open, unsubscribe
from email_engine.webhooks import email_webhook
from leads.assignment_views import AssignmentSettingsView
from leads.auth_views import RoleBasedLoginView
from leads.settings_views import (
    DangerZoneView,
    OrganisationProfileSettingsView,
    SettingsHubView,
)
from leads.invites import (
    InviteAcceptView,
    TeamInviteCreateView,
    TeamInviteListView,
    TeamInviteResendView,
    TeamInviteRevokeView,
)
from leads.lists import (
    ContactListCreateView,
    ContactListDetailView,
    ContactListIndexView,
)
from leads.views import AgentHomeView, AppHomeView, SignupView, landing_page
from leads.marketing_views import MarketingFeaturesView, MarketingPricingView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", landing_page, name="landing_page"),
    path("features/", MarketingFeaturesView.as_view(), name="marketing_features"),
    path("pricing/", MarketingPricingView.as_view(), name="marketing_pricing"),
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
        "app/settings/",
        SettingsHubView.as_view(),
        name="settings_hub",
    ),
    path(
        "app/settings/profile/",
        OrganisationProfileSettingsView.as_view(),
        name="settings_profile",
    ),
    path(
        "app/settings/danger/",
        DangerZoneView.as_view(),
        name="settings_danger",
    ),
    path(
        "app/settings/assignment/",
        AssignmentSettingsView.as_view(),
        name="assignment_settings",
    ),
    path(
        "app/settings/compliance/",
        ComplianceSettingsView.as_view(),
        name="compliance_settings",
    ),
    path("app/lists/", ContactListIndexView.as_view(), name="list_index"),
    path("app/lists/create/", ContactListCreateView.as_view(), name="list_create"),
    path(
        "app/lists/<int:pk>/",
        ContactListDetailView.as_view(),
        name="list_detail",
    ),
    path(
        "app/email-templates/",
        EmailTemplateIndexView.as_view(),
        name="email_template_index",
    ),
    path(
        "app/email-templates/create/",
        EmailTemplateCreateView.as_view(),
        name="email_template_create",
    ),
    path(
        "app/email-templates/<int:pk>/",
        EmailTemplateDetailView.as_view(),
        name="email_template_detail",
    ),
    path("app/campaigns/", CampaignIndexView.as_view(), name="campaign_index"),
    path(
        "app/campaigns/create/",
        CampaignCreateView.as_view(),
        name="campaign_create",
    ),
    path(
        "app/campaigns/<int:pk>/",
        CampaignDetailView.as_view(),
        name="campaign_detail",
    ),
    path(
        "app/campaigns/<int:pk>/report/",
        CampaignReportView.as_view(),
        name="campaign_report",
    ),
    path("app/sequences/", SequenceIndexView.as_view(), name="sequence_index"),
    path(
        "app/sequences/create/",
        SequenceCreateView.as_view(),
        name="sequence_create",
    ),
    path(
        "app/sequences/<int:pk>/",
        SequenceDetailView.as_view(),
        name="sequence_detail",
    ),
    path("app/billing/", BillingPlansView.as_view(), name="billing_plans"),
    path("app/billing/usage/", BillingUsageView.as_view(), name="billing_usage"),
    path("app/audit/", AuditLogView.as_view(), name="audit_log"),
    path("app/audit/export/", AuditExportView.as_view(), name="audit_export"),
    path(
        "app/notifications/",
        NotificationInboxView.as_view(),
        name="app_notifications",
    ),
    # Agent workspace
    path("agent/", AgentHomeView.as_view(), name="agent_home"),
    path(
        "agent/notifications/",
        NotificationInboxView.as_view(),
        name="agent_notifications",
    ),
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
    path("webhooks/stripe/", stripe_webhook, name="stripe_webhook"),
    path("t/o/<uuid:token>.gif", track_open, name="email_track_open"),
    path("t/c/<uuid:token>/", track_click, name="email_track_click"),
    path("t/u/<uuid:token>/", unsubscribe, name="email_unsubscribe"),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
