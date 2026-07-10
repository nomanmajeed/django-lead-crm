import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from email_engine.merge import build_merge_context, render_merge
from email_engine.models import (
    Campaign,
    CampaignRecipient,
    EmailDeliveryEvent,
    EmailTemplate,
    OutboundEmail,
)
from email_engine.service import queue_transactional_email
from leads.models import ContactList, ContactListMembership, Lead, Organisation

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


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_PROVIDER="console",
    CELERY_TASK_ALWAYS_EAGER=True,
    EMAIL_ASYNC=True,
)
class CampaignOneShotTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="camp_owner",
            password="pass12345",
            email="camp@example.com",
            is_organisor=True,
        )
        self.organisation = Organisation.objects.get(owner=self.owner)
        self.template = EmailTemplate.objects.create(
            organisation=self.organisation,
            name="Blast",
            subject="Hi {{first_name}}",
            body_html="<p>Hello {{first_name}}</p>",
            body_text="Hello {{first_name}}",
        )
        self.contact_list = ContactList.objects.create(
            organisation=self.organisation,
            name="Prospects",
            kind=ContactList.Kind.STATIC,
        )
        self.leads = []
        for i in range(3):
            lead = Lead.objects.create(
                first_name=f"Lead{i}",
                last_name="Test",
                age=30,
                organisation=self.organisation,
                description="x",
                phone_number=str(i),
                email=f"lead{i}@example.com",
            )
            ContactListMembership.objects.create(
                contact_list=self.contact_list, lead=lead
            )
            self.leads.append(lead)

    def test_send_now_delivers_to_all_and_marks_sent(self):
        self.client.login(username="camp_owner", password="pass12345")
        create = self.client.post(
            reverse("campaign_create"),
            {
                "name": "Spring blast",
                "contact_list": self.contact_list.pk,
                "template": self.template.pk,
            },
        )
        self.assertEqual(create.status_code, 302)
        campaign = Campaign.objects.get(name="Spring blast")
        self.assertEqual(campaign.status, Campaign.Status.DRAFT)

        response = self.client.post(
            reverse("campaign_detail", kwargs={"pk": campaign.pk}),
            {"action": "send_now"},
        )
        self.assertEqual(response.status_code, 302)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, Campaign.Status.SENT)
        self.assertEqual(
            campaign.recipients.filter(status=CampaignRecipient.Status.SENT).count(),
            3,
        )
        self.assertEqual(
            OutboundEmail.objects.filter(organisation=self.organisation).count(),
            3,
        )
        subjects = set(
            OutboundEmail.objects.filter(organisation=self.organisation).values_list(
                "subject", flat=True
            )
        )
        self.assertEqual(subjects, {"Hi Lead0", "Hi Lead1", "Hi Lead2"})

    def test_cancel_stops_further_sends(self):
        from email_engine.campaigns import (
            cancel_campaign,
            materialize_recipients,
            process_campaign_batch,
        )

        campaign = Campaign.objects.create(
            organisation=self.organisation,
            name="Partial",
            contact_list=self.contact_list,
            template=self.template,
            batch_size=1,
            batch_delay_seconds=0,
            status=Campaign.Status.SENDING,
        )
        materialize_recipients(campaign)
        self.assertEqual(campaign.recipients.count(), 3)

        process_campaign_batch(campaign.pk, chain=False)
        campaign.refresh_from_db()
        self.assertEqual(
            campaign.recipients.filter(status=CampaignRecipient.Status.SENT).count(),
            1,
        )
        self.assertEqual(campaign.status, Campaign.Status.SENDING)

        cancel_campaign(campaign)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, Campaign.Status.CANCELLED)

        result = process_campaign_batch(campaign.pk)
        self.assertEqual(result, "cancelled")
        campaign.refresh_from_db()
        self.assertEqual(
            campaign.recipients.filter(status=CampaignRecipient.Status.SENT).count(),
            1,
        )
        self.assertEqual(
            campaign.recipients.filter(
                status=CampaignRecipient.Status.SKIPPED
            ).count(),
            2,
        )
        self.assertEqual(
            OutboundEmail.objects.filter(organisation=self.organisation).count(),
            1,
        )

    def test_status_transitions_draft_to_sending_to_sent(self):
        from email_engine.campaigns import schedule_or_send_campaign

        campaign = Campaign.objects.create(
            organisation=self.organisation,
            name="Flow",
            contact_list=self.contact_list,
            template=self.template,
            batch_size=25,
            status=Campaign.Status.DRAFT,
        )
        schedule_or_send_campaign(campaign, send_now=True)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, Campaign.Status.SENT)
        self.assertIsNotNone(campaign.started_at)
        self.assertIsNotNone(campaign.completed_at)
