from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from leads.models import Agent, Lead, Membership, Organisation
from leads.permissions import (
    get_user_organisation,
    user_can_manage_organisation,
    user_is_agent_member,
)

User = get_user_model()


class MembershipPermissionsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner",
            password="pass12345",
            is_organisor=True,
            is_agent=False,
        )
        self.organisation = Organisation.objects.get(owner=self.owner)

        self.agent_user = User.objects.create_user(
            username="agent1",
            password="pass12345",
            is_organisor=False,
            is_agent=True,
        )
        Agent.objects.create(user=self.agent_user, organisation=self.organisation)
        Membership.objects.create(
            user=self.agent_user,
            organisation=self.organisation,
            role=Membership.Role.AGENT,
        )

    def test_owner_can_manage(self):
        self.assertTrue(
            user_can_manage_organisation(self.owner, self.organisation)
        )
        self.assertFalse(user_is_agent_member(self.owner, self.organisation))

    def test_agent_cannot_manage(self):
        self.assertFalse(
            user_can_manage_organisation(self.agent_user, self.organisation)
        )
        self.assertTrue(
            user_is_agent_member(self.agent_user, self.organisation)
        )
        self.assertEqual(
            get_user_organisation(self.agent_user), self.organisation
        )

    def test_agent_redirected_from_agent_list(self):
        self.client.login(username="agent1", password="pass12345")
        response = self.client.get(reverse("agents:agent_list"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("leads:lead_list"))

    def test_owner_can_open_agent_list(self):
        self.client.login(username="owner", password="pass12345")
        response = self.client.get(reverse("agents:agent_list"))
        self.assertEqual(response.status_code, 200)


class TenantIsolationTests(TestCase):
    def setUp(self):
        self.owner_a = User.objects.create_user(
            username="owner_a",
            password="pass12345",
            is_organisor=True,
        )
        self.org_a = Organisation.objects.get(owner=self.owner_a)
        self.lead_a = Lead.objects.create(
            first_name="Ada",
            last_name="A",
            age=30,
            organisation=self.org_a,
            description="Org A lead",
            phone_number="111",
            email="a@example.com",
        )

        self.owner_b = User.objects.create_user(
            username="owner_b",
            password="pass12345",
            is_organisor=True,
        )
        self.org_b = Organisation.objects.get(owner=self.owner_b)
        self.lead_b = Lead.objects.create(
            first_name="Bob",
            last_name="B",
            age=40,
            organisation=self.org_b,
            description="Org B lead",
            phone_number="222",
            email="b@example.com",
        )

    def test_for_org_excludes_other_tenant(self):
        self.assertEqual(Lead.objects.for_org(self.org_a).count(), 1)
        self.assertTrue(Lead.objects.for_org(self.org_a).filter(pk=self.lead_a.pk).exists())
        self.assertFalse(
            Lead.objects.for_org(self.org_a).filter(pk=self.lead_b.pk).exists()
        )

    def test_owner_cannot_view_other_org_lead_detail(self):
        self.client.login(username="owner_a", password="pass12345")
        response = self.client.get(
            reverse("leads:lead_detail", kwargs={"pk": self.lead_b.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_owner_can_view_own_lead_detail(self):
        self.client.login(username="owner_a", password="pass12345")
        response = self.client.get(
            reverse("leads:lead_detail", kwargs={"pk": self.lead_a.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_lead_list_only_shows_own_org(self):
        self.client.login(username="owner_a", password="pass12345")
        # Unassigned leads appear in unassigned bucket for organisers
        response = self.client.get(reverse("leads:lead_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ada")
        self.assertNotContains(response, "Bob")
