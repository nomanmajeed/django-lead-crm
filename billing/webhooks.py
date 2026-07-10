"""Stripe webhook endpoint."""

import logging

from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from billing.stripe_service import (
    StripeNotConfigured,
    construct_webhook_event,
    handle_stripe_event,
    stripe_enabled,
)

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def stripe_webhook(request):
    if not stripe_enabled():
        return HttpResponseBadRequest("Stripe is not configured.")

    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    try:
        event = construct_webhook_event(payload, sig_header)
    except StripeNotConfigured as exc:
        return HttpResponseBadRequest(str(exc))
    except ValueError:
        return HttpResponseBadRequest("Invalid payload.")
    except Exception as exc:  # stripe.error.SignatureVerificationError
        # Import lazily so tests can mock without stripe installed edge cases
        try:
            import stripe

            if isinstance(exc, stripe.error.SignatureVerificationError):
                return HttpResponseForbidden("Invalid signature.")
        except Exception:
            pass
        logger.warning("Stripe webhook rejected: %s", exc)
        return HttpResponseForbidden("Invalid signature.")

    # construct_event returns a StripeObject; normalize to dict
    if hasattr(event, "to_dict"):
        event_data = event.to_dict()
    else:
        event_data = event

    result = handle_stripe_event(event_data)
    logger.info("Stripe webhook handled: %s", result)
    return HttpResponse(status=200)
