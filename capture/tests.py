from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from capture.models import LeadCaptureForm
from capture.service import check_rate_limit, increment_rate_limit
from leads.models import Lead, Organisation

User = get_user_model()


class PublicCaptureFormTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="capture_owner",
            password="pass12345",
            is_organisor=True,
        )
        self.organisation = Organisation.objects.get(owner=self.owner)
        self.other_owner = User.objects.create_user(
            username="capture_other",
            password="pass12345",
            is_organisor=True,
        )
        self.other_org = Organisation.objects.get(owner=self.other_owner)
        self.capture = LeadCaptureForm.objects.create(
            organisation=self.organisation,
            name="Website",
        )

    def test_public_submit_creates_lead_in_correct_org(self):
        url = reverse("public_capture", kwargs={"public_key": self.capture.public_key})
        response = self.client.post(
            url,
            {
                "first_name": "Pat",
                "last_name": "Lee",
                "email": "pat@example.com",
                "phone_number": "555",
                "description": "From site",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Thank you")
        lead = Lead.objects.get(email="pat@example.com")
        self.assertEqual(lead.organisation_id, self.organisation.pk)
        self.assertFalse(
            Lead.objects.filter(
                email="pat@example.com", organisation=self.other_org
            ).exists()
        )

    def test_honeypot_blocks_spam(self):
        url = reverse("public_capture", kwargs={"public_key": self.capture.public_key})
        response = self.client.post(
            url,
            {
                "first_name": "Bot",
                "last_name": "Spam",
                "email": "bot@example.com",
                "phone_number": "1",
                "company_url": "http://spam.test",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Lead.objects.filter(email="bot@example.com").exists())

    @override_settings(CAPTURE_FORM_RATE_LIMIT=2)
    def test_rate_limit_blocks_excess_submissions(self):
        url = reverse("public_capture", kwargs={"public_key": self.capture.public_key})
        payload = {
            "first_name": "R",
            "last_name": "L",
            "email": "rate@example.com",
            "phone_number": "9",
        }
        self.assertEqual(self.client.post(url, payload).status_code, 200)
        payload["email"] = "rate2@example.com"
        self.assertEqual(self.client.post(url, payload).status_code, 200)
        payload["email"] = "rate3@example.com"
        blocked = self.client.post(url, payload)
        self.assertEqual(blocked.status_code, 403)

    def test_inactive_form_not_found(self):
        self.capture.is_active = False
        self.capture.save(update_fields=["is_active"])
        url = reverse("public_capture", kwargs={"public_key": self.capture.public_key})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_organiser_can_create_and_see_embed(self):
        self.client.login(username="capture_owner", password="pass12345")
        response = self.client.post(
            reverse("capture_create"),
            {"name": "Landing", "is_active": "on"},
        )
        self.assertEqual(response.status_code, 302)
        created = LeadCaptureForm.objects.get(name="Landing")
        detail = self.client.get(reverse("capture_detail", kwargs={"pk": created.pk}))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "iframe")
        self.assertContains(detail, str(created.public_key))

    def test_rate_limit_helpers(self):
        with self.settings(CAPTURE_FORM_RATE_LIMIT=2):
            self.assertTrue(check_rate_limit(self.capture, "1.2.3.4"))
            increment_rate_limit(self.capture, "1.2.3.4")
            increment_rate_limit(self.capture, "1.2.3.4")
            self.assertFalse(check_rate_limit(self.capture, "1.2.3.4"))
