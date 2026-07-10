"""Provider webhook endpoints for delivery events (bounce, complaint, etc.)."""

import json

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from email_engine.models import EmailDeliveryEvent, OutboundEmail

EVENT_ALIASES = {
    "sent": EmailDeliveryEvent.EventType.SENT,
    "processed": EmailDeliveryEvent.EventType.SENT,
    "delivered": EmailDeliveryEvent.EventType.DELIVERED,
    "delivery": EmailDeliveryEvent.EventType.DELIVERED,
    "bounce": EmailDeliveryEvent.EventType.BOUNCE,
    "bounced": EmailDeliveryEvent.EventType.BOUNCE,
    "complaint": EmailDeliveryEvent.EventType.COMPLAINT,
    "spamcomplaint": EmailDeliveryEvent.EventType.COMPLAINT,
    "spam_complaint": EmailDeliveryEvent.EventType.COMPLAINT,
    "open": EmailDeliveryEvent.EventType.OPEN,
    "click": EmailDeliveryEvent.EventType.CLICK,
    "failed": EmailDeliveryEvent.EventType.FAILED,
    "dropped": EmailDeliveryEvent.EventType.FAILED,
}


def _authorized(request) -> bool:
    secret = getattr(settings, "EMAIL_WEBHOOK_SECRET", "") or ""
    if not secret:
        # Local/dev: allow without secret so console testing works.
        return True
    header = request.headers.get("X-Leadcrm-Webhook-Secret", "")
    query = request.GET.get("secret", "")
    return header == secret or query == secret


def _record_event(provider: str, event_type: str, message_id: str, payload: dict):
    mapped = EVENT_ALIASES.get(event_type.lower())
    if mapped is None:
        return None
    outbound = None
    if message_id:
        outbound = OutboundEmail.objects.filter(provider_message_id=message_id).first()
    return EmailDeliveryEvent.objects.create(
        outbound_email=outbound,
        provider=provider,
        provider_message_id=message_id or "",
        event_type=mapped,
        payload=payload,
    )


@csrf_exempt
@require_POST
def email_webhook(request, provider: str):
    if not _authorized(request):
        return HttpResponseForbidden("Invalid webhook secret")

    provider = provider.lower()
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    created = 0

    # Generic single-event payload
    if isinstance(payload, dict) and (
        "event" in payload or "event_type" in payload or "RecordType" in payload
    ):
        event_type = (
            payload.get("event")
            or payload.get("event_type")
            or payload.get("RecordType")
            or ""
        )
        message_id = (
            payload.get("provider_message_id")
            or payload.get("MessageID")
            or payload.get("sg_message_id")
            or payload.get("mail", {}).get("messageId", "")
            or ""
        )
        if _record_event(provider, str(event_type), str(message_id), payload):
            created += 1

    # SendGrid-style list of events
    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            event_type = item.get("event") or item.get("event_type") or ""
            message_id = (
                item.get("sg_message_id")
                or item.get("provider_message_id")
                or item.get("MessageID")
                or ""
            )
            if _record_event(provider, str(event_type), str(message_id), item):
                created += 1

    return JsonResponse({"ok": True, "recorded": created})


@csrf_exempt
@require_POST
def email_webhook_health(request):
    return HttpResponse("ok")
