"""Open/click tracking, unsubscribe links, and compliance footers."""

from __future__ import annotations

import re
import uuid
from html import escape
from urllib.parse import quote, unquote, urlparse

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from email_engine.models import EmailDeliveryEvent, OutboundEmail

# 1x1 transparent GIF
PIXEL_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00"
    b"!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01"
    b"\x00\x00\x02\x02D\x01\x00;"
)

HREF_RE = re.compile(
    r'href=(["\'])(https?://[^"\']+)\1',
    re.IGNORECASE,
)


def public_base_url() -> str:
    return getattr(settings, "PUBLIC_BASE_URL", "http://127.0.0.1:8001").rstrip("/")


def tracking_url(name: str, token, **kwargs) -> str:
    path = reverse(name, kwargs={"token": str(token), **kwargs})
    return f"{public_base_url()}{path}"


def open_pixel_url(token) -> str:
    return tracking_url("email_track_open", token)


def click_wrap_url(token, target_url: str) -> str:
    path = reverse("email_track_click", kwargs={"token": str(token)})
    return f"{public_base_url()}{path}?u={quote(target_url, safe='')}"


def unsubscribe_url(token) -> str:
    return tracking_url("email_unsubscribe", token)


def ensure_tracking_token(outbound: OutboundEmail) -> OutboundEmail:
    if outbound.tracking_token:
        return outbound
    outbound.tracking_token = uuid.uuid4()
    outbound.tracking_enabled = True
    outbound.save(update_fields=["tracking_token", "tracking_enabled"])
    return outbound


def _compliance_footer_html(outbound: OutboundEmail) -> str:
    org = outbound.organisation
    org_name = escape(org.name if org else "Lead CRM")
    address = (org.physical_address if org else "") or ""
    address_html = escape(address).replace("\n", "<br>") if address else (
        "<em>Physical address not configured</em>"
    )
    unsub = unsubscribe_url(outbound.tracking_token)
    return (
        '<div style="margin-top:24px;padding-top:16px;border-top:1px solid #ddd;'
        'font-size:12px;color:#666;font-family:system-ui,sans-serif;line-height:1.5">'
        f"<p>{org_name}</p>"
        f"<p>{address_html}</p>"
        f'<p><a href="{escape(unsub)}">Unsubscribe</a> from future emails.</p>'
        "</div>"
    )


def _compliance_footer_text(outbound: OutboundEmail) -> str:
    org = outbound.organisation
    org_name = org.name if org else "Lead CRM"
    address = (org.physical_address if org else "") or "Physical address not configured"
    unsub = unsubscribe_url(outbound.tracking_token)
    return (
        f"\n\n--\n{org_name}\n{address}\n"
        f"Unsubscribe: {unsub}\n"
    )


def apply_tracking(outbound: OutboundEmail) -> OutboundEmail:
    """Rewrite HTML/text with pixel, wrapped links, and compliance footer."""
    if not outbound.tracking_enabled:
        return outbound
    ensure_tracking_token(outbound)
    html = outbound.body_html or ""
    text = outbound.body_text or ""

    def wrap_href(match):
        quote_char = match.group(1)
        url = match.group(2)
        wrapped = click_wrap_url(outbound.tracking_token, url)
        return f"href={quote_char}{wrapped}{quote_char}"

    if html:
        html = HREF_RE.sub(wrap_href, html)
        pixel = (
            f'<img src="{escape(open_pixel_url(outbound.tracking_token))}" '
            'width="1" height="1" alt="" style="display:none" />'
        )
        footer = _compliance_footer_html(outbound)
        if re.search(r"</body\s*>", html, re.I):
            html = re.sub(
                r"</body\s*>",
                f"{pixel}{footer}</body>",
                html,
                count=1,
                flags=re.I,
            )
        else:
            html = f"{html}{pixel}{footer}"
        outbound.body_html = html

    text = (text or "") + _compliance_footer_text(outbound)
    outbound.body_text = text
    outbound.save(update_fields=["body_html", "body_text"])
    return outbound


def record_open(outbound: OutboundEmail, *, payload: dict | None = None):
    EmailDeliveryEvent.objects.create(
        outbound_email=outbound,
        provider=outbound.provider or "tracking",
        provider_message_id=outbound.provider_message_id,
        event_type=EmailDeliveryEvent.EventType.OPEN,
        payload=payload or {"source": "pixel"},
    )


def record_click(outbound: OutboundEmail, target_url: str):
    EmailDeliveryEvent.objects.create(
        outbound_email=outbound,
        provider=outbound.provider or "tracking",
        provider_message_id=outbound.provider_message_id,
        event_type=EmailDeliveryEvent.EventType.CLICK,
        payload={"url": target_url, "source": "wrap"},
    )


def safe_redirect_url(raw: str, fallback: str = "/") -> str:
    url = unquote(raw or "").strip()
    parsed = urlparse(url)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return url
    return fallback


def process_unsubscribe(outbound: OutboundEmail) -> None:
    from email_engine.models import SequenceEnrollment
    from email_engine.sequences import cancel_enrollment, suppress_email
    from leads.models import Lead

    org = outbound.organisation
    if org:
        suppress_email(org, outbound.to_email, reason="unsubscribe")
        lead_ids = Lead.objects.for_org(org).filter(
            email__iexact=outbound.to_email
        ).values_list("pk", flat=True)
        for enrollment in SequenceEnrollment.objects.filter(
            lead_id__in=lead_ids,
            status=SequenceEnrollment.Status.ACTIVE,
            sequence__organisation=org,
        ):
            cancel_enrollment(enrollment)

    EmailDeliveryEvent.objects.create(
        outbound_email=outbound,
        provider=outbound.provider or "tracking",
        provider_message_id=outbound.provider_message_id,
        event_type=EmailDeliveryEvent.EventType.UNSUBSCRIBE,
        payload={"email": outbound.to_email, "at": timezone.now().isoformat()},
    )
