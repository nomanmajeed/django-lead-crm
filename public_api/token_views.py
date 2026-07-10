from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from agents.mixins import OrganisorAndLoginRequiredMixin, OwnerRequiredMixin
from public_api.models import APIToken


class APITokenCreateForm(forms.Form):
    name = forms.CharField(
        max_length=120,
        widget=forms.TextInput(
            attrs={"class": "input input-bordered w-full", "placeholder": "Zapier"}
        ),
    )


class APITokenIndexView(OrganisorAndLoginRequiredMixin, View):
    def get(self, request):
        tokens = APIToken.objects.filter(organisation=request.organisation)
        return render(
            request,
            "app/api/tokens.html",
            {
                "topbar_title": "API tokens",
                "tokens": tokens,
                "form": APITokenCreateForm(),
                "new_token": request.session.pop("new_api_token", None),
            },
        )


class APITokenCreateView(OrganisorAndLoginRequiredMixin, View):
    def post(self, request):
        form = APITokenCreateForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Token name is required.")
            return redirect("api_tokens")
        token, raw = APIToken.create_for_org(
            request.organisation,
            name=form.cleaned_data["name"],
            created_by=request.user,
        )
        request.session["new_api_token"] = raw
        messages.success(
            request,
            f"Token “{token.name}” created. Copy it now — it won't be shown again.",
        )
        return redirect("api_tokens")


class APITokenRevokeView(OwnerRequiredMixin, View):
    def post(self, request, pk):
        token = get_object_or_404(
            APIToken,
            pk=pk,
            organisation=request.organisation,
            revoked_at__isnull=True,
        )
        token.revoked_at = timezone.now()
        token.save(update_fields=["revoked_at"])
        messages.success(request, f"Revoked token “{token.name}”.")
        return redirect("api_tokens")
