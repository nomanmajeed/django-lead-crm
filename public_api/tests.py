from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from email_engine.models import Campaign, EmailTemplate
from leads.models import ContactList, Lead, Membership, Organisation
from public_api.models import APIToken

User = get_user_model()


class PublicAPITests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="api_owner",
            password="pass12345",
            is_organisor=True,
        )
        self.organisation = Organisation.objects.get(owner=self.owner)
        self.other = User.objects.create_user(
            username="api_other",
            password="pass12345",
            is_organisor=True,
        )
        self.other_org = Organisation.objects.get(owner=self.other)
        self.token, self.raw = APIToken.create_for_org(
            self.organisation, name="Test", created_by=self.owner
        )
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {self.raw}"}

    def test_missing_token_returns_401(self):
        response = self.client.get(reverse("api_leads"))
        self.assertEqual(response.status_code, 401)

    def test_leads_crud_scoped_to_token_org(self):
        create = self.client.post(
            reverse("api_leads"),
            data={
                "first_name": "Api",
                "last_name": "Lead",
                "email": "api@example.com",
                "phone_number": "1",
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(create.status_code, 201)
        lead_id = create.json()["id"]
        self.assertEqual(
            Lead.objects.get(pk=lead_id).organisation_id, self.organisation.pk
        )

        other_lead = Lead.objects.create(
            first_name="X",
            last_name="Y",
            age=1,
            organisation=self.other_org,
            description="x",
            phone_number="2",
            email="other@example.com",
        )
        blocked = self.client.get(
            reverse("api_lead_detail", kwargs={"pk": other_lead.pk}),
            **self.auth,
        )
        self.assertEqual(blocked.status_code, 404)

        patch = self.client.patch(
            reverse("api_lead_detail", kwargs={"pk": lead_id}),
            data='{"description": "Updated"}',
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(patch.status_code, 200)
        self.assertEqual(patch.json()["description"], "Updated")

        delete = self.client.delete(
            reverse("api_lead_detail", kwargs={"pk": lead_id}),
            **self.auth,
        )
        self.assertEqual(delete.status_code, 204)
        self.assertFalse(Lead.objects.filter(pk=lead_id).exists())

    def test_campaign_create_and_list(self):
        template = EmailTemplate.objects.create(
            organisation=self.organisation,
            name="T",
            subject="Hi",
            body_html="<p>Hi</p>",
            body_text="Hi",
        )
        contact_list = ContactList.objects.create(
            organisation=self.organisation,
            name="L",
            kind=ContactList.Kind.STATIC,
        )
        response = self.client.post(
            reverse("api_campaigns"),
            data={
                "name": "API campaign",
                "contact_list_id": contact_list.pk,
                "template_id": template.pk,
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], Campaign.Status.DRAFT)

        listing = self.client.get(reverse("api_campaigns"), **self.auth)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.json()["results"]), 1)

    def test_revoked_token_rejected(self):
        from django.utils import timezone

        self.token.revoked_at = timezone.now()
        self.token.save(update_fields=["revoked_at"])
        response = self.client.get(reverse("api_leads"), **self.auth)
        self.assertEqual(response.status_code, 401)

    def test_openapi_schema_with_token(self):
        response = self.client.get(reverse("api_openapi"), **self.auth)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["openapi"], "3.0.3")

    def test_owner_can_create_token_in_app(self):
        self.client.login(username="api_owner", password="pass12345")
        response = self.client.post(
            reverse("api_token_create"),
            {"name": "Zapier"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            APIToken.objects.filter(
                organisation=self.organisation, name="Zapier"
            ).exists()
        )
