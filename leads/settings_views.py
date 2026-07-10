"""Organisation settings hub: profile, links, and owner danger zone."""

from django import forms
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect, render
from django.views import View

from agents.mixins import OrganisorAndLoginRequiredMixin, OwnerRequiredMixin
from leads.models import Membership, Organisation
from leads.permissions import user_is_org_owner

COMMON_TIMEZONES = [
    ("UTC", "UTC"),
    ("America/New_York", "America/New_York"),
    ("America/Chicago", "America/Chicago"),
    ("America/Denver", "America/Denver"),
    ("America/Los_Angeles", "America/Los_Angeles"),
    ("Europe/London", "Europe/London"),
    ("Europe/Paris", "Europe/Paris"),
    ("Asia/Karachi", "Asia/Karachi"),
    ("Asia/Dubai", "Asia/Dubai"),
    ("Asia/Singapore", "Asia/Singapore"),
    ("Australia/Sydney", "Australia/Sydney"),
]


class OrganisationProfileForm(forms.ModelForm):
    class Meta:
        model = Organisation
        fields = (
            "name",
            "timezone",
            "primary_color",
            "from_name",
            "from_email",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tz = self.fields["timezone"]
        choices = list(COMMON_TIMEZONES)
        current = (self.instance.timezone if self.instance else "") or "UTC"
        if current and current not in {c[0] for c in choices}:
            choices.insert(0, (current, current))
        tz.widget = forms.Select(
            choices=choices,
            attrs={"class": "select select-bordered w-full"},
        )
        self.fields["name"].widget.attrs.update(
            {"class": "input input-bordered w-full"}
        )
        self.fields["primary_color"].widget.attrs.update(
            {"class": "input input-bordered w-full", "type": "color"}
        )
        self.fields["from_name"].widget.attrs.update(
            {
                "class": "input input-bordered w-full",
                "placeholder": "Acme Sales",
            }
        )
        self.fields["from_email"].widget.attrs.update(
            {
                "class": "input input-bordered w-full",
                "placeholder": "hello@acme.example",
            }
        )

    def clean_primary_color(self):
        color = (self.cleaned_data.get("primary_color") or "").strip()
        if not color:
            return "#0F766E"
        if not color.startswith("#") or len(color) not in (4, 7):
            raise forms.ValidationError("Use a hex color like #0F766E.")
        return color


class DeleteOrganisationForm(forms.Form):
    confirm_name = forms.CharField(
        label="Type the organisation name to confirm",
        widget=forms.TextInput(
            attrs={
                "class": "input input-bordered w-full",
                "autocomplete": "off",
            }
        ),
    )

    def __init__(self, *args, organisation=None, **kwargs):
        self.organisation = organisation
        super().__init__(*args, **kwargs)

    def clean_confirm_name(self):
        value = (self.cleaned_data.get("confirm_name") or "").strip()
        if self.organisation and value != self.organisation.name:
            raise forms.ValidationError(
                "Name does not match. Type the exact organisation name."
            )
        return value


class SettingsHubView(OrganisorAndLoginRequiredMixin, View):
    def get(self, request):
        org = request.organisation
        return render(
            request,
            "app/settings/index.html",
            {
                "topbar_title": "Settings",
                "organisation": org,
                "is_owner": user_is_org_owner(request.user, org),
                "member_count": Membership.objects.filter(
                    organisation=org
                ).count(),
            },
        )


class OrganisationProfileSettingsView(OrganisorAndLoginRequiredMixin, View):
    def get(self, request):
        return render(
            request,
            "app/settings/profile.html",
            {
                "topbar_title": "Organisation profile",
                "form": OrganisationProfileForm(instance=request.organisation),
                "organisation": request.organisation,
            },
        )

    def post(self, request):
        form = OrganisationProfileForm(
            request.POST, instance=request.organisation
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Organisation profile saved.")
            return redirect("settings_profile")
        return render(
            request,
            "app/settings/profile.html",
            {
                "topbar_title": "Organisation profile",
                "form": form,
                "organisation": request.organisation,
            },
        )


class DangerZoneView(OwnerRequiredMixin, View):
    def get(self, request):
        return render(
            request,
            "app/settings/danger.html",
            {
                "topbar_title": "Danger zone",
                "organisation": request.organisation,
                "form": DeleteOrganisationForm(
                    organisation=request.organisation
                ),
            },
        )

    def post(self, request):
        org = request.organisation
        form = DeleteOrganisationForm(request.POST, organisation=org)
        if not form.is_valid():
            return render(
                request,
                "app/settings/danger.html",
                {
                    "topbar_title": "Danger zone",
                    "organisation": org,
                    "form": form,
                },
            )
        name = org.name
        org.delete()
        logout(request)
        messages.success(
            request,
            f"Organisation “{name}” was permanently deleted.",
        )
        return redirect("landing_page")
