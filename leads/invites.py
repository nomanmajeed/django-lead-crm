import secrets
from datetime import timedelta

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.forms import UsernameField
from django.shortcuts import get_object_or_404, redirect, reverse
from django.utils import timezone
from django.views import generic

from agents.mixins import OrganisorAndLoginRequiredMixin
from email_engine.service import queue_transactional_email

from .models import Agent, Invite, Membership

User = get_user_model()

INVITE_TTL_DAYS = 7


def build_invite_token():
    return secrets.token_urlsafe(32)


def send_invite_email(request, invite):
    accept_url = request.build_absolute_uri(
        reverse("invite_accept", kwargs={"token": invite.token})
    )
    queue_transactional_email(
        to_email=invite.email,
        subject=f"You're invited to {invite.organisation.name} on Lead CRM",
        body_text=(
            f"You've been invited to join {invite.organisation.name} "
            f"as {invite.get_role_display()}.\n\n"
            f"Accept the invite: {accept_url}\n\n"
            f"This link expires on {invite.expires_at:%Y-%m-%d %H:%M %Z}."
        ),
        organisation=invite.organisation,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@leadcrm.local"),
    )


class InviteCreateForm(forms.ModelForm):
    class Meta:
        model = Invite
        fields = ("email", "role")

    def __init__(self, *args, organisation=None, **kwargs):
        self.organisation = organisation
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if Membership.objects.filter(
            organisation=self.organisation,
            user__email__iexact=email,
        ).exists():
            raise forms.ValidationError("This person is already a member.")
        if Invite.objects.filter(
            organisation=self.organisation,
            email__iexact=email,
            accepted_at__isnull=True,
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).exists():
            raise forms.ValidationError("A pending invite already exists for this email.")
        return email


class AcceptInviteForm(forms.Form):
    username = UsernameField()
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password1") != cleaned.get("password2"):
            self.add_error("password2", "Passwords do not match.")
        username = cleaned.get("username")
        if username and User.objects.filter(username=username).exists():
            self.add_error("username", "Username already taken.")
        return cleaned


def accept_invite_for_user(invite, user):
    Membership.objects.update_or_create(
        user=user,
        organisation=invite.organisation,
        defaults={"role": invite.role},
    )
    if invite.role == Invite.Role.AGENT:
        agent, created = Agent.objects.get_or_create(
            user=user,
            defaults={"organisation": invite.organisation},
        )
        if not created and agent.organisation_id != invite.organisation_id:
            agent.organisation = invite.organisation
            agent.save(update_fields=["organisation"])

    invite.accepted_at = timezone.now()
    invite.save(update_fields=["accepted_at"])


class TeamInviteListView(OrganisorAndLoginRequiredMixin, generic.ListView):
    template_name = "app/team.html"
    context_object_name = "invites"

    def get_queryset(self):
        return Invite.objects.filter(
            organisation=self.request.organisation
        ).select_related("invited_by")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "topbar_title": "Team",
                "form": InviteCreateForm(),
                "members": Membership.objects.filter(
                    organisation=self.request.organisation
                ).select_related("user"),
            }
        )
        return context


class TeamInviteCreateView(OrganisorAndLoginRequiredMixin, generic.View):
    def post(self, request, *args, **kwargs):
        form = InviteCreateForm(
            request.POST, organisation=request.organisation
        )
        if not form.is_valid():
            messages.error(request, "Could not create invite. Check the form and try again.")
            return redirect("team")

        invite = form.save(commit=False)
        invite.organisation = request.organisation
        invite.invited_by = request.user
        invite.token = build_invite_token()
        invite.expires_at = timezone.now() + timedelta(days=INVITE_TTL_DAYS)
        invite.save()
        send_invite_email(request, invite)
        messages.success(request, f"Invite sent to {invite.email}.")
        return redirect("team")


class TeamInviteRevokeView(OrganisorAndLoginRequiredMixin, generic.View):
    def post(self, request, pk, *args, **kwargs):
        invite = get_object_or_404(
            Invite,
            pk=pk,
            organisation=request.organisation,
            accepted_at__isnull=True,
            revoked_at__isnull=True,
        )
        invite.revoked_at = timezone.now()
        invite.save(update_fields=["revoked_at"])
        messages.success(request, f"Invite to {invite.email} revoked.")
        return redirect("team")


class TeamInviteResendView(OrganisorAndLoginRequiredMixin, generic.View):
    def post(self, request, pk, *args, **kwargs):
        invite = get_object_or_404(
            Invite,
            pk=pk,
            organisation=request.organisation,
            accepted_at__isnull=True,
            revoked_at__isnull=True,
        )
        invite.token = build_invite_token()
        invite.expires_at = timezone.now() + timedelta(days=INVITE_TTL_DAYS)
        invite.save(update_fields=["token", "expires_at"])
        send_invite_email(request, invite)
        messages.success(request, f"Invite resent to {invite.email}.")
        return redirect("team")


class InviteAcceptView(generic.FormView):
    template_name = "registration/invite_accept.html"
    form_class = AcceptInviteForm

    def dispatch(self, request, *args, **kwargs):
        self.invite = get_object_or_404(Invite, token=kwargs["token"])
        if self.invite.revoked_at is not None:
            messages.error(request, "This invite has been revoked.")
            return redirect("landing_page")
        if self.invite.accepted_at is not None:
            messages.info(request, "This invite was already accepted.")
            return redirect("login")
        if self.invite.expires_at <= timezone.now():
            messages.error(request, "This invite has expired.")
            return redirect("landing_page")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["invite"] = self.invite
        return context

    def form_valid(self, form):
        if self.request.user.is_authenticated:
            user = self.request.user
            if user.email and user.email.lower() != self.invite.email.lower():
                messages.error(
                    self.request,
                    "Signed-in email does not match the invite. Log out and try again.",
                )
                return redirect("invite_accept", token=self.invite.token)
        else:
            user = User(
                username=form.cleaned_data["username"],
                email=self.invite.email,
                is_organisor=False,
                is_agent=self.invite.role == Invite.Role.AGENT,
            )
            user.set_password(form.cleaned_data["password1"])
            user.save()

        accept_invite_for_user(self.invite, user)
        login(self.request, user)
        messages.success(
            self.request,
            f"Welcome to {self.invite.organisation.name}!",
        )
        if self.invite.role == Invite.Role.ADMIN:
            return redirect("app_home")
        return redirect("agent_home")

    def get(self, request, *args, **kwargs):
        # Logged-in matching user can accept with one click via POST confirm
        if request.user.is_authenticated:
            return self.render_to_response(self.get_context_data(form=None))
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.POST.get("confirm_join"):
            if (
                request.user.email
                and request.user.email.lower() != self.invite.email.lower()
            ):
                messages.error(
                    request,
                    "Signed-in email does not match the invite. Log out and try again.",
                )
                return redirect("invite_accept", token=self.invite.token)
            accept_invite_for_user(self.invite, request.user)
            messages.success(
                request, f"Welcome to {self.invite.organisation.name}!"
            )
            if self.invite.role == Invite.Role.ADMIN:
                return redirect("app_home")
            return redirect("agent_home")
        return super().post(request, *args, **kwargs)
