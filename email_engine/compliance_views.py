"""Organiser compliance settings: physical address + suppression list."""

from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from agents.mixins import OrganisorAndLoginRequiredMixin
from email_engine.models import EmailSuppression
from email_engine.sequences import suppress_email
from leads.models import Organisation


class ComplianceForm(forms.ModelForm):
    class Meta:
        model = Organisation
        fields = ("physical_address",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["physical_address"].widget = forms.Textarea(
            attrs={
                "class": "textarea textarea-bordered w-full",
                "rows": 3,
                "placeholder": "123 Main St\nCity, ST 00000\nCountry",
            }
        )


class ComplianceSettingsView(OrganisorAndLoginRequiredMixin, View):
    def get(self, request):
        suppressions = EmailSuppression.objects.filter(
            organisation=request.organisation
        ).order_by("-created_at")[:100]
        return render(
            request,
            "app/compliance/settings.html",
            {
                "topbar_title": "Email compliance",
                "form": ComplianceForm(instance=request.organisation),
                "suppressions": suppressions,
            },
        )

    def post(self, request):
        action = request.POST.get("action", "save_address")
        if action == "save_address":
            form = ComplianceForm(request.POST, instance=request.organisation)
            if form.is_valid():
                form.save()
                messages.success(request, "Physical address saved.")
                return redirect("compliance_settings")
            suppressions = EmailSuppression.objects.filter(
                organisation=request.organisation
            ).order_by("-created_at")[:100]
            return render(
                request,
                "app/compliance/settings.html",
                {
                    "topbar_title": "Email compliance",
                    "form": form,
                    "suppressions": suppressions,
                },
            )

        if action == "add_suppression":
            email = (request.POST.get("email") or "").strip()
            if email:
                suppress_email(
                    request.organisation, email, reason="manual"
                )
                messages.success(request, f"Suppressed {email}.")
            else:
                messages.error(request, "Email is required.")
            return redirect("compliance_settings")

        if action == "remove_suppression":
            row = get_object_or_404(
                EmailSuppression,
                pk=request.POST.get("suppression_id"),
                organisation=request.organisation,
            )
            email = row.email
            row.delete()
            messages.success(request, f"Removed {email} from suppression list.")
            return redirect("compliance_settings")

        messages.error(request, "Unknown action.")
        return redirect("compliance_settings")
