"""Organiser billing / plan overview (Stripe checkout comes in a later ticket)."""

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View

from agents.mixins import OrganisorAndLoginRequiredMixin
from billing.entitlements import all_plans, get_entitlements
from email_engine.models import Campaign, EmailSequence, OutboundEmail
from leads.models import Agent, Lead, Membership


class BillingPlansView(OrganisorAndLoginRequiredMixin, View):
    def get(self, request):
        org = request.organisation
        entitlements = get_entitlements(org)
        usage = {
            "seats": Membership.objects.filter(organisation=org).count()
            if org
            else 0,
            "leads": Lead.objects.for_org(org).count() if org else 0,
            "agents": Agent.objects.for_org(org).count() if org else 0,
            "campaigns": Campaign.objects.filter(organisation=org).count()
            if org
            else 0,
            "sequences": EmailSequence.objects.filter(organisation=org).count()
            if org
            else 0,
            "monthly_emails": OutboundEmail.objects.filter(
                organisation=org, status=OutboundEmail.Status.SENT
            ).count()
            if org
            else 0,
        }
        return render(
            request,
            "app/billing/plans.html",
            {
                "topbar_title": "Plans & billing",
                "organisation": org,
                "entitlements": entitlements,
                "plans": all_plans(),
                "usage": usage,
            },
        )

    def post(self, request):
        # Placeholder until Stripe Checkout (ticket 27).
        messages.info(
            request,
            "Stripe checkout is coming next — plan changes will be available there.",
        )
        return redirect("billing_plans")
