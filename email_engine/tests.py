import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from email_engine.merge import build_merge_context, render_merge
from email_engine.models import EmailDeliveryEvent, EmailTemplate, OutboundEmail
from email_engine.service import queue_transactional_email
from leads.models import Lead, Organisation

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


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_PROVIDER="console",
    CELERY_TASK_ALWAYS_EAGER=True,
    EMAIL_ASYNC=True,
)
class EmailTemplateTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="tpl_owner",
            password="pass12345",
            email="owner@example.com",
            is_organisor=True,
        )
        self.organisation = Organisation.objects.get(owner=self.owner)
        Lead.objects.create(
            first_name="Ada",
            last_name="Lovelace",
            age=36,
            organisation=self.organisation,
            description="sample",
            phone_number="555",
            email="ada@example.com",
            custom_fields={"company": "Analytical Engines"},
        )

    def test_owner_saves_template_and_preview_merges(self):
        self.client.login(username="tpl_owner", password="pass12345")
        response = self.client.post(
            reverse("email_template_create"),
            {
                "name": "Welcome",
                "subject": "Hi {{first_name}}",
                "body_html": "<p>Hello {{first_name}} from {{organisation_name}}</p>",
                "body_text": "Hello {{first_name}}",
            },
        )
        self.assertEqual(response.status_code, 302)
        template = EmailTemplate.objects.get(name="Welcome")
        self.assertEqual(template.organisation_id, self.organisation.pk)

        detail = self.client.get(
            reverse("email_template_detail", kwargs={"pk": template.pk})
        )
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Hi Ada")
        self.assertContains(detail, "Hello Ada from")
        # Escaped merge values should not break the page
        self.assertContains(detail, "<p>Hello Ada from")

    def test_test_send_delivers_merged_fields(self):
        self.client.login(username="tpl_owner", password="pass12345")
        template = EmailTemplate.objects.create(
            organisation=self.organisation,
            name="Ping",
            subject="Hey {{first_name}}",
            body_html="<p>{{full_name}} · {{company}}</p>",
            body_text="{{full_name}}",
        )
        response = self.client.post(
            reverse("email_template_detail", kwargs={"pk": template.pk}),
            {"action": "test_send"},
        )
        self.assertEqual(response.status_code, 302)
        outbound = OutboundEmail.objects.filter(to_email="owner@example.com").latest(
            "created_at"
        )
        self.assertEqual(outbound.status, OutboundEmail.Status.SENT)
        self.assertEqual(outbound.subject, "Hey Ada")
        self.assertIn("Ada Lovelace", outbound.body_html)
        self.assertIn("Analytical Engines", outbound.body_html)

    def test_merge_escapes_dangerous_values(self):
        context = build_merge_context()
        context["first_name"] = "<script>alert(1)</script>"
        from email_engine.template_views import _safe_preview_html

        html = _safe_preview_html("<p>Hi {{first_name}}</p>", context)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)
