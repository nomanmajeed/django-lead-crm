from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from leads.models import Agent, Membership, Organisation
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
        # Signal creates org + owner membership for organisers
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
        self.assertFalse(
            user_is_agent_member(self.owner, self.organisation)
        )

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
