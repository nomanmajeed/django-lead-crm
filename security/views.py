from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from agents.mixins import OwnerRequiredMixin
from security.totp import generate_totp_secret, provisioning_uri, verify_totp

User = get_user_model()
PENDING_2FA_SESSION_KEY = "pending_2fa_user_id"
PENDING_2FA_SECRET_KEY = "pending_totp_secret"


class TOTPCodeForm(forms.Form):
    code = forms.CharField(
        max_length=8,
        label="Authentication code",
        widget=forms.TextInput(
            attrs={
                "class": "input input-bordered w-full",
                "autocomplete": "one-time-code",
                "inputmode": "numeric",
            }
        ),
    )


class TwoFactorVerifyView(View):
    """Complete login after password when 2FA is enabled."""

    template_name = "registration/two_factor_verify.html"

    def _pending_user(self, request):
        user_id = request.session.get(PENDING_2FA_SESSION_KEY)
        if not user_id:
            return None
        return User.objects.filter(pk=user_id, totp_enabled=True).first()

    def get(self, request):
        if self._pending_user(request) is None:
            return redirect("login")
        return render(request, self.template_name, {"form": TOTPCodeForm()})

    def post(self, request):
        user = self._pending_user(request)
        if user is None:
            return redirect("login")
        form = TOTPCodeForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})
        if not verify_totp(user.totp_secret, form.cleaned_data["code"]):
            messages.error(request, "Invalid authentication code.")
            return render(request, self.template_name, {"form": form})
        request.session.pop(PENDING_2FA_SESSION_KEY, None)
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        if user.is_organisor:
            return redirect("app_home")
        return redirect("agent_home")


class SecuritySettingsView(OwnerRequiredMixin, View):
    template_name = "app/settings/security.html"

    def get(self, request):
        pending_secret = request.session.get(PENDING_2FA_SECRET_KEY, "")
        return render(
            request,
            self.template_name,
            {
                "topbar_title": "Security",
                "user": request.user,
                "pending_secret": pending_secret,
                "provisioning_uri": provisioning_uri(
                    secret=pending_secret, user=request.user
                )
                if pending_secret
                else "",
                "form": TOTPCodeForm(),
            },
        )

    def post(self, request):
        action = request.POST.get("action", "")
        user = request.user

        if action == "start_enable":
            secret = generate_totp_secret()
            request.session[PENDING_2FA_SECRET_KEY] = secret
            messages.info(request, "Scan or enter the key, then confirm with a code.")
            return redirect("settings_security")

        if action == "confirm_enable":
            secret = request.session.get(PENDING_2FA_SECRET_KEY, "")
            form = TOTPCodeForm(request.POST)
            if not secret or not form.is_valid():
                messages.error(request, "Enter a valid code to enable 2FA.")
                return redirect("settings_security")
            if not verify_totp(secret, form.cleaned_data["code"]):
                messages.error(request, "Code did not match. Try again.")
                return redirect("settings_security")
            user.totp_secret = secret
            user.totp_enabled = True
            user.save(update_fields=["totp_secret", "totp_enabled"])
            request.session.pop(PENDING_2FA_SECRET_KEY, None)
            messages.success(request, "Two-factor authentication enabled.")
            return redirect("settings_security")

        if action == "disable":
            form = TOTPCodeForm(request.POST)
            if not form.is_valid() or not verify_totp(
                user.totp_secret, form.cleaned_data["code"]
            ):
                messages.error(request, "Valid code required to disable 2FA.")
                return redirect("settings_security")
            user.totp_secret = ""
            user.totp_enabled = False
            user.save(update_fields=["totp_secret", "totp_enabled"])
            request.session.pop(PENDING_2FA_SECRET_KEY, None)
            messages.success(request, "Two-factor authentication disabled.")
            return redirect("settings_security")

        messages.error(request, "Unknown action.")
        return redirect("settings_security")
