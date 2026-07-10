import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from email_engine.models import EmailDeliveryEvent, OutboundEmail
from email_engine.service import queue_transactional_email
from leads.models import Organisation

User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_PROVIDER="console",
    CELERY_TASK_ALWAYS_EAGER=True,
    EMAIL_ASYNC=True,
    EMAIL_WEBHOOK_SECRET="",
)
class EmailEngineTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="mail_owner",
            password="pass12345",
            is_organisor=True,
        )
        self.organisation = Organisation.objects.get(owner=self.owner)

    def test_queue_sends_via_console_provider_and_records_sent_event(self):
        outbound = queue_transactional_email(
            to_email="prospect@example.com",
            subject="Hello",
            body_text="Welcome",
            organisation=self.organisation,
        )
        outbound.refresh_from_db()
        self.assertEqual(outbound.status, OutboundEmail.Status.SENT)
        self.assertTrue(outbound.provider_message_id)
        self.assertTrue(
            EmailDeliveryEvent.objects.filter(
                outbound_email=outbound,
                event_type=EmailDeliveryEvent.EventType.SENT,
            ).exists()
        )

    def test_webhook_records_bounce_against_message_id(self):
        outbound = queue_transactional_email(
            to_email="bounce@example.com",
            subject="Ping",
            body_text="Ping",
            organisation=self.organisation,
        )
        outbound.refresh_from_db()
        response = self.client.post(
            reverse("email_webhook", kwargs={"provider": "sendgrid"}),
            data=json.dumps(
                [
                    {
                        "event": "bounce",
                        "sg_message_id": outbound.provider_message_id,
                        "email": "bounce@example.com",
                    }
                ]
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            EmailDeliveryEvent.objects.filter(
                outbound_email=outbound,
                event_type=EmailDeliveryEvent.EventType.BOUNCE,
                provider="sendgrid",
            ).exists()
        )

    def test_webhook_rejects_bad_secret_when_configured(self):
        with self.settings(EMAIL_WEBHOOK_SECRET="topsecret"):
            response = self.client.post(
                reverse("email_webhook", kwargs={"provider": "postmark"}),
                data=json.dumps({"event": "delivered", "MessageID": "x"}),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 403)
