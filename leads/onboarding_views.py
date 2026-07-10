from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone
from django.views import View

from agents.mixins import OwnerRequiredMixin


class OnboardingDismissView(OwnerRequiredMixin, View):
    def post(self, request):
        org = request.organisation
        org.onboarding_dismissed_at = timezone.now()
        org.save(update_fields=["onboarding_dismissed_at", "updated_at"])
        messages.success(request, "Onboarding checklist dismissed.")
        return redirect("app_home")
