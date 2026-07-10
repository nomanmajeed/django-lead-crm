"""Organiser billing / plan overview with Stripe Checkout + Customer Portal."""

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from agents.mixins import OrganisorAndLoginRequiredMixin
from billing.entitlements import all_plans, get_entitlements
from billing.stripe_service import (
    StripeNotConfigured,
    apply_subscription_to_org,
    create_checkout_session,
    create_portal_session,
    downgrade_to_free,
    stripe_enabled,
)
from email_engine.models import Campaign, EmailSequence, OutboundEmail
from leads.models import Agent, Lead, Membership, Organisation


class BillingPlansView(OrganisorAndLoginRequiredMixin, View):
    def _usage(self, org):
        return {
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

    def get(self, request):
        org = request.organisation
        entitlements = get_entitlements(org)
        return render(
            request,
            "app/billing/plans.html",
            {
                "topbar_title": "Plans & billing",
                "organisation": org,
                "entitlements": entitlements,
                "plans": all_plans(),
                "usage": self._usage(org),
                "stripe_enabled": stripe_enabled(),
                "stripe_simulate": getattr(
                    settings, "STRIPE_BILLING_SIMULATE", False
                )
                and not stripe_enabled(),
            },
        )

    def post(self, request):
        org = request.organisation
        action = request.POST.get("action", "change_plan")
        plan = (request.POST.get("plan") or "").strip()

        if action == "portal":
            if not stripe_enabled():
                messages.error(request, "Stripe is not configured.")
                return redirect("billing_plans")
            try:
                url = create_portal_session(
                    org,
                    return_url=request.build_absolute_uri(
                        reverse("billing_plans")
                    ),
                )
                return redirect(url)
            except (StripeNotConfigured, ValueError) as exc:
                messages.error(request, str(exc))
                return redirect("billing_plans")

        if plan not in {
            Organisation.Plan.FREE,
            Organisation.Plan.PRO,
            Organisation.Plan.BUSINESS,
        }:
            messages.error(request, "Unknown plan.")
            return redirect("billing_plans")

        # Paid upgrade via Checkout when Stripe is configured
        if stripe_enabled() and plan != Organisation.Plan.FREE:
            try:
                url = create_checkout_session(
                    org,
                    plan=plan,
                    success_url=request.build_absolute_uri(
                        reverse("billing_plans")
                    )
                    + "?checkout=success",
                    cancel_url=request.build_absolute_uri(
                        reverse("billing_plans")
                    )
                    + "?checkout=cancel",
                    customer_email=request.user.email or "",
                )
                return redirect(url)
            except (StripeNotConfigured, ValueError) as exc:
                messages.error(request, str(exc))
                return redirect("billing_plans")

        # Downgrade / manage via portal when subscribed
        if stripe_enabled() and plan == Organisation.Plan.FREE:
            if org.stripe_customer_id:
                try:
                    url = create_portal_session(
                        org,
                        return_url=request.build_absolute_uri(
                            reverse("billing_plans")
                        ),
                    )
                    return redirect(url)
                except (StripeNotConfigured, ValueError) as exc:
                    messages.error(request, str(exc))
                    return redirect("billing_plans")
            downgrade_to_free(org)
            messages.success(request, "Plan set to Free.")
            return redirect("billing_plans")

        # Local/dev simulation when Stripe keys are absent
        if getattr(settings, "STRIPE_BILLING_SIMULATE", False):
            if plan == Organisation.Plan.FREE:
                downgrade_to_free(org)
            else:
                apply_subscription_to_org(
                    org,
                    plan=plan,
                    subscription_id=f"sim_sub_{plan}",
                )
            messages.success(
                request,
                f"Plan updated to {plan.title()} (simulated — configure Stripe for live checkout).",
            )
            return redirect("billing_plans")

        messages.error(
            request,
            "Stripe is not configured. Set STRIPE_SECRET_KEY and price IDs.",
        )
        return redirect("billing_plans")
