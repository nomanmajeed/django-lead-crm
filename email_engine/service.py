"""Transactional email API used by the rest of the product."""

from django.conf import settings
from django.utils import timezone

from email_engine.models import EmailDeliveryEvent, OutboundEmail, default_from_email
from email_engine.providers import get_email_provider


def queue_transactional_email(
    *,
    to_email: str,
    subject: str,
    body_text: str,
    body_html: str = "",
    organisation=None,
    from_email: str | None = None,
    async_send: bool | None = None,
):
    """
    Persist an outbound email and send via Celery (or eagerly in local/dev).

    Returns the OutboundEmail row.
    """
    provider = get_email_provider()
    outbound = OutboundEmail.objects.create(
        organisation=organisation,
        to_email=to_email,
        from_email=from_email or default_from_email(),
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        provider=provider.name,
        status=OutboundEmail.Status.QUEUED,
    )

    use_async = (
        getattr(settings, "EMAIL_ASYNC", True)
        if async_send is None
        else async_send
    )
    if use_async:
        from email_engine.tasks import send_outbound_email_task

        send_outbound_email_task.delay(outbound.pk)
        # Eager mode mutates the row in-process; refresh so callers see final status.
        outbound.refresh_from_db()
    else:
        deliver_outbound_email(outbound.pk)
        outbound.refresh_from_db()
    return outbound


def deliver_outbound_email(outbound_id: int) -> OutboundEmail:
    outbound = OutboundEmail.objects.get(pk=outbound_id)
    provider = get_email_provider(outbound.provider)
    result = provider.send(
        to_email=outbound.to_email,
        from_email=outbound.from_email,
        subject=outbound.subject,
        body_text=outbound.body_text,
        body_html=outbound.body_html,
    )
    if result.success:
        outbound.status = OutboundEmail.Status.SENT
        outbound.provider_message_id = result.provider_message_id
        outbound.sent_at = timezone.now()
        outbound.error_message = ""
        outbound.save(
            update_fields=[
                "status",
                "provider_message_id",
                "sent_at",
                "error_message",
            ]
        )
        EmailDeliveryEvent.objects.create(
            outbound_email=outbound,
            provider=outbound.provider,
            provider_message_id=outbound.provider_message_id,
            event_type=EmailDeliveryEvent.EventType.SENT,
            payload={"source": "provider_send"},
        )
    else:
        outbound.status = OutboundEmail.Status.FAILED
        outbound.error_message = result.error_message
        outbound.save(update_fields=["status", "error_message"])
        EmailDeliveryEvent.objects.create(
            outbound_email=outbound,
            provider=outbound.provider,
            provider_message_id=outbound.provider_message_id,
            event_type=EmailDeliveryEvent.EventType.FAILED,
            payload={"error": result.error_message},
        )
    return outbound
