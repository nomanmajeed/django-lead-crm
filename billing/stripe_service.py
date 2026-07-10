"""Stripe Checkout, Customer Portal, and subscription → plan sync."""

from __future__ import annotations

from django.conf import settings

from leads.models import Organisation


class StripeNotConfigured(Exception):
    pass


def stripe_enabled() -> bool:
    return bool(getattr(settings, "STRIPE_SECRET_KEY", ""))


def price_id_for_plan(plan: str) -> str:
    mapping = {
        Organisation.Plan.PRO: getattr(settings, "STRIPE_PRICE_PRO", ""),
        Organisation.Plan.BUSINESS: getattr(settings, "STRIPE_PRICE_BUSINESS", ""),
    }
    return mapping.get(plan, "") or ""


def plan_for_price_id(price_id: str) -> str:
    if not price_id:
        return Organisation.Plan.FREE
    if price_id == getattr(settings, "STRIPE_PRICE_PRO", ""):
        return Organisation.Plan.PRO
    if price_id == getattr(settings, "STRIPE_PRICE_BUSINESS", ""):
        return Organisation.Plan.BUSINESS
    return Organisation.Plan.FREE


def _stripe():
    if not stripe_enabled():
        raise StripeNotConfigured("STRIPE_SECRET_KEY is not set.")
    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def ensure_customer(organisation, *, email: str = "") -> str:
    """Return Stripe customer id, creating one if needed."""
    if organisation.stripe_customer_id:
        return organisation.stripe_customer_id
    stripe = _stripe()
    customer = stripe.Customer.create(
        email=email or None,
        name=organisation.name,
        metadata={
            "organisation_id": str(organisation.pk),
            "organisation_slug": organisation.slug,
        },
    )
    organisation.stripe_customer_id = customer["id"]
    organisation.save(update_fields=["stripe_customer_id", "updated_at"])
    return organisation.stripe_customer_id


def create_checkout_session(
    organisation,
    *,
    plan: str,
    success_url: str,
    cancel_url: str,
    customer_email: str = "",
) -> str:
    """Create a Checkout Session for a paid plan; returns the session URL."""
    price_id = price_id_for_plan(plan)
    if plan == Organisation.Plan.FREE:
        raise ValueError("Use the customer portal to cancel/downgrade to Free.")
    if not price_id:
        raise ValueError(f"No Stripe price configured for plan “{plan}”.")

    stripe = _stripe()
    customer_id = ensure_customer(organisation, email=customer_email)
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=str(organisation.pk),
        metadata={
            "organisation_id": str(organisation.pk),
            "plan": plan,
        },
        subscription_data={
            "metadata": {
                "organisation_id": str(organisation.pk),
                "plan": plan,
            }
        },
    )
    return session["url"]


def create_portal_session(organisation, *, return_url: str) -> str:
    stripe = _stripe()
    if not organisation.stripe_customer_id:
        raise ValueError("No Stripe customer on this organisation yet.")
    session = stripe.billing_portal.Session.create(
        customer=organisation.stripe_customer_id,
        return_url=return_url,
    )
    return session["url"]


def apply_subscription_to_org(
    organisation,
    *,
    plan: str,
    customer_id: str = "",
    subscription_id: str = "",
) -> Organisation:
    previous = organisation.plan
    update_fields = ["plan", "updated_at"]
    organisation.plan = plan
    if customer_id:
        organisation.stripe_customer_id = customer_id
        update_fields.append("stripe_customer_id")
    if subscription_id is not None:
        organisation.stripe_subscription_id = subscription_id
        update_fields.append("stripe_subscription_id")
    organisation.save(update_fields=update_fields)
    if previous != plan:
        from notifications.service import notify_billing_change

        notify_billing_change(organisation, plan=plan, actor_label="Stripe")
    return organisation


def downgrade_to_free(organisation) -> Organisation:
    previous = organisation.plan
    organisation.plan = Organisation.Plan.FREE
    organisation.stripe_subscription_id = ""
    organisation.save(
        update_fields=["plan", "stripe_subscription_id", "updated_at"]
    )
    if previous != Organisation.Plan.FREE:
        from notifications.service import notify_billing_change

        notify_billing_change(
            organisation, plan=Organisation.Plan.FREE, actor_label="Billing"
        )
    return organisation


def _org_from_metadata(metadata: dict | None):
    metadata = metadata or {}
    org_id = metadata.get("organisation_id")
    if not org_id:
        return None
    return Organisation.objects.filter(pk=org_id).first()


def handle_stripe_event(event: dict) -> str:
    """
    Apply a verified Stripe event to local org state.
    Returns a short status string for logging/tests.
    """
    etype = event.get("type", "")
    data = (event.get("data") or {}).get("object") or {}

    if etype == "checkout.session.completed":
        org = _org_from_metadata(data.get("metadata"))
        if org is None and data.get("client_reference_id"):
            org = Organisation.objects.filter(
                pk=data["client_reference_id"]
            ).first()
        if org is None:
            return "ignored:no_org"
        plan = (data.get("metadata") or {}).get("plan") or Organisation.Plan.PRO
        apply_subscription_to_org(
            org,
            plan=plan,
            customer_id=data.get("customer") or "",
            subscription_id=data.get("subscription") or "",
        )
        return f"checkout:{plan}"

    if etype in {
        "customer.subscription.updated",
        "customer.subscription.created",
    }:
        org = _org_from_metadata(data.get("metadata"))
        if org is None and data.get("customer"):
            org = Organisation.objects.filter(
                stripe_customer_id=data["customer"]
            ).first()
        if org is None:
            return "ignored:no_org"
        status = data.get("status", "")
        if status in {"canceled", "unpaid", "incomplete_expired"}:
            downgrade_to_free(org)
            return "subscription:free"
        items = (data.get("items") or {}).get("data") or []
        price_id = ""
        if items:
            price_id = ((items[0].get("price") or {}).get("id")) or ""
        plan = plan_for_price_id(price_id)
        if plan == Organisation.Plan.FREE and data.get("metadata", {}).get("plan"):
            plan = data["metadata"]["plan"]
        apply_subscription_to_org(
            org,
            plan=plan,
            customer_id=data.get("customer") or org.stripe_customer_id,
            subscription_id=data.get("id") or "",
        )
        return f"subscription:{plan}"

    if etype == "customer.subscription.deleted":
        org = _org_from_metadata(data.get("metadata"))
        if org is None and data.get("customer"):
            org = Organisation.objects.filter(
                stripe_customer_id=data["customer"]
            ).first()
        if org is None:
            return "ignored:no_org"
        downgrade_to_free(org)
        return "subscription:deleted"

    return f"ignored:{etype}"


def construct_webhook_event(payload: bytes, sig_header: str):
    stripe = _stripe()
    secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
    if not secret:
        raise StripeNotConfigured("STRIPE_WEBHOOK_SECRET is not set.")
    return stripe.Webhook.construct_event(payload, sig_header, secret)
