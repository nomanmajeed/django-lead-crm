"""Public marketing pages (landing companions)."""

from django.shortcuts import render
from django.views import View

from billing.entitlements import PLAN_CATALOG
from leads.models import Organisation


class MarketingPricingView(View):
    def get(self, request):
        plans = [
            PLAN_CATALOG[Organisation.Plan.FREE],
            PLAN_CATALOG[Organisation.Plan.PRO],
            PLAN_CATALOG[Organisation.Plan.BUSINESS],
        ]
        return render(
            request,
            "marketing/pricing.html",
            {"plans": plans},
        )


class MarketingFeaturesView(View):
    def get(self, request):
        return render(request, "marketing/features.html")
