"""Pluggable email providers: console, smtp, sendgrid, postmark."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Protocol
from urllib import error, request

from django.conf import settings
from django.core.mail import EmailMultiAlternatives


@dataclass
class SendResult:
    success: bool
    provider_message_id: str = ""
    error_message: str = ""


class EmailProvider(Protocol):
    name: str

    def send(
        self,
        *,
        to_email: str,
        from_email: str,
        subject: str,
        body_text: str,
        body_html: str = "",
    ) -> SendResult: ...


class ConsoleProvider:
    name = "console"

    def send(self, *, to_email, from_email, subject, body_text, body_html=""):
        message = EmailMultiAlternatives(
            subject=subject,
            body=body_text or subject,
            from_email=from_email,
            to=[to_email],
        )
        if body_html:
            message.attach_alternative(body_html, "text/html")
        message.send(fail_silently=False)
        return SendResult(success=True, provider_message_id=f"console-{uuid.uuid4().hex}")


class SMTPProvider:
    name = "smtp"

    def send(self, *, to_email, from_email, subject, body_text, body_html=""):
        message = EmailMultiAlternatives(
            subject=subject,
            body=body_text or subject,
            from_email=from_email,
            to=[to_email],
        )
        if body_html:
            message.attach_alternative(body_html, "text/html")
        message.send(fail_silently=False)
        return SendResult(success=True, provider_message_id=f"smtp-{uuid.uuid4().hex}")


class SendGridProvider:
    name = "sendgrid"

    def send(self, *, to_email, from_email, subject, body_text, body_html=""):
        api_key = getattr(settings, "SENDGRID_API_KEY", "") or ""
        if not api_key:
            # Local/staging without key: fall through to Django email backend.
            fallback = ConsoleProvider().send(
                to_email=to_email,
                from_email=from_email,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
            )
            return SendResult(
                success=fallback.success,
                provider_message_id=fallback.provider_message_id.replace(
                    "console-", "sendgrid-fallback-"
                ),
                error_message=fallback.error_message,
            )

        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": from_email},
            "subject": subject,
            "content": [{"type": "text/plain", "value": body_text or subject}],
        }
        if body_html:
            payload["content"].append({"type": "text/html", "value": body_html})
        req = request.Request(
            "https://api.sendgrid.com/v3/mail/send",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=20) as resp:
                message_id = resp.headers.get("X-Message-Id") or f"sendgrid-{uuid.uuid4().hex}"
                return SendResult(success=True, provider_message_id=message_id)
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            return SendResult(success=False, error_message=f"SendGrid {exc.code}: {detail}")
        except error.URLError as exc:
            return SendResult(success=False, error_message=str(exc.reason))


class PostmarkProvider:
    name = "postmark"

    def send(self, *, to_email, from_email, subject, body_text, body_html=""):
        token = getattr(settings, "POSTMARK_SERVER_TOKEN", "") or ""
        if not token:
            fallback = ConsoleProvider().send(
                to_email=to_email,
                from_email=from_email,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
            )
            return SendResult(
                success=fallback.success,
                provider_message_id=fallback.provider_message_id.replace(
                    "console-", "postmark-fallback-"
                ),
                error_message=fallback.error_message,
            )

        payload = {
            "From": from_email,
            "To": to_email,
            "Subject": subject,
            "TextBody": body_text or subject,
            "HtmlBody": body_html or None,
            "MessageStream": "outbound",
        }
        req = request.Request(
            "https://api.postmarkapp.com/email",
            data=json.dumps({k: v for k, v in payload.items() if v is not None}).encode(
                "utf-8"
            ),
            headers={
                "X-Postmark-Server-Token": token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return SendResult(
                    success=True,
                    provider_message_id=str(data.get("MessageID") or uuid.uuid4().hex),
                )
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            return SendResult(success=False, error_message=f"Postmark {exc.code}: {detail}")
        except error.URLError as exc:
            return SendResult(success=False, error_message=str(exc.reason))


PROVIDERS = {
    "console": ConsoleProvider,
    "smtp": SMTPProvider,
    "sendgrid": SendGridProvider,
    "postmark": PostmarkProvider,
}


def get_email_provider(name: str | None = None) -> EmailProvider:
    provider_name = (name or getattr(settings, "EMAIL_PROVIDER", "console")).lower()
    cls = PROVIDERS.get(provider_name, ConsoleProvider)
    return cls()
