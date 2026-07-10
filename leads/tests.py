from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from leads.models import Agent, Category, Invite, Lead, Membership, Organisation
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
        self.assertEqual(response.url, reverse("agent_home"))

    def test_owner_can_open_agent_list(self):
        self.client.login(username="owner", password="pass12345")
        response = self.client.get(reverse("agents:agent_list"))
        self.assertEqual(response.status_code, 200)

    def test_agent_blocked_from_app_home(self):
        self.client.login(username="agent1", password="pass12345")
        response = self.client.get(reverse("app_home"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("agent_home"))

    def test_agent_can_open_agent_home(self):
        self.client.login(username="agent1", password="pass12345")
        response = self.client.get(reverse("agent_home"))
        self.assertEqual(response.status_code, 200)

    def test_login_redirects_agent_to_agent_home(self):
        response = self.client.post(
            reverse("login"),
            {"username": "agent1", "password": "pass12345"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("agent_home"))

    def test_login_redirects_owner_to_app_home(self):
        response = self.client.post(
            reverse("login"),
            {"username": "owner", "password": "pass12345"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("app_home"))


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


class SignupOnboardingTests(TestCase):
    def test_signup_creates_org_membership_and_lands_on_app(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "newco",
                "email": "founder@newco.test",
                "company_name": "NewCo Labs",
                "password1": "complex-pass-12345",
                "password2": "complex-pass-12345",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("app_home"))

        user = User.objects.get(username="newco")
        organisation = user.owned_organisation
        self.assertEqual(organisation.name, "NewCo Labs")
        self.assertTrue(
            Membership.objects.filter(
                user=user,
                organisation=organisation,
                role=Membership.Role.OWNER,
            ).exists()
        )

        follow = self.client.get(reverse("app_home"))
        self.assertEqual(follow.status_code, 200)
        self.assertContains(follow, "NewCo Labs")
        self.assertContains(follow, "No leads yet")


class OrganiserDashboardTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="dash_owner",
            password="pass12345",
            is_organisor=True,
        )
        self.organisation = Organisation.objects.get(owner=self.owner)
        Lead.objects.create(
            first_name="Pat",
            last_name="Pipeline",
            age=28,
            organisation=self.organisation,
            description="Dashboard lead",
            phone_number="555",
            email="pat@example.com",
        )

    def test_dashboard_shows_live_metrics(self):
        self.client.login(username="dash_owner", password="pass12345")
        response = self.client.get(reverse("app_home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "New leads (7d)")
        self.assertContains(response, "Open pipeline")
        self.assertContains(response, "Pat Pipeline")
        self.assertContains(response, "Add lead")
        self.assertEqual(response.context["new_leads"], 1)
        self.assertEqual(response.context["open_pipeline"], 1)
        self.assertEqual(response.context["campaign_sends"], 0)


class TeamInviteTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="boss",
            password="pass12345",
            email="boss@co.test",
            is_organisor=True,
        )
        self.organisation = Organisation.objects.get(owner=self.owner)

    def test_owner_can_invite_and_agent_accepts(self):
        self.client.login(username="boss", password="pass12345")
        response = self.client.post(
            reverse("team_invite_create"),
            {"email": "agent@co.test", "role": "agent"},
        )
        self.assertEqual(response.status_code, 302)
        invite = Invite.objects.get(email="agent@co.test")
        self.assertTrue(invite.is_usable())

        self.client.logout()
        response = self.client.post(
            reverse("invite_accept", kwargs={"token": invite.token}),
            {
                "username": "hired_agent",
                "password1": "complex-pass-12345",
                "password2": "complex-pass-12345",
            },
        )
        self.assertEqual(response.status_code, 302)
        invite.refresh_from_db()
        self.assertIsNotNone(invite.accepted_at)
        agent_user = User.objects.get(username="hired_agent")
        self.assertTrue(
            Membership.objects.filter(
                user=agent_user,
                organisation=self.organisation,
                role=Membership.Role.AGENT,
            ).exists()
        )
        self.assertTrue(Agent.objects.filter(user=agent_user).exists())
        self.assertEqual(response.url, reverse("agent_home"))

    def test_revoked_invite_rejected(self):
        self.client.login(username="boss", password="pass12345")
        self.client.post(
            reverse("team_invite_create"),
            {"email": "gone@co.test", "role": "agent"},
        )
        invite = Invite.objects.get(email="gone@co.test")
        self.client.post(reverse("team_invite_revoke", kwargs={"pk": invite.pk}))
        invite.refresh_from_db()
        self.assertIsNotNone(invite.revoked_at)

        self.client.logout()
        response = self.client.get(
            reverse("invite_accept", kwargs={"token": invite.token})
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("landing_page"))

    def test_expired_invite_rejected(self):
        from datetime import timedelta

        from django.utils import timezone

        from leads.invites import build_invite_token

        invite = Invite.objects.create(
            organisation=self.organisation,
            email="old@co.test",
            role=Invite.Role.AGENT,
            token=build_invite_token(),
            invited_by=self.owner,
            expires_at=timezone.now() - timedelta(hours=1),
        )
        response = self.client.get(
            reverse("invite_accept", kwargs={"token": invite.token})
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("landing_page"))

    def test_team_page_lists_invites(self):
        self.client.login(username="boss", password="pass12345")
        self.client.post(
            reverse("team_invite_create"),
            {"email": "listme@co.test", "role": "agent"},
        )
        response = self.client.get(reverse("team"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "listme@co.test")


class AgentDashboardTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="agent_boss",
            password="pass12345",
            is_organisor=True,
        )
        self.organisation = Organisation.objects.get(owner=self.owner)
        self.agent_user = User.objects.create_user(
            username="worker",
            password="pass12345",
            is_organisor=False,
            is_agent=True,
        )
        self.agent = Agent.objects.create(
            user=self.agent_user, organisation=self.organisation
        )
        Membership.objects.create(
            user=self.agent_user,
            organisation=self.organisation,
            role=Membership.Role.AGENT,
        )
        self.category = Category.objects.create(
            name="Contacted", organisation=self.organisation
        )
        self.mine = Lead.objects.create(
            first_name="Mine",
            last_name="Lead",
            age=30,
            organisation=self.organisation,
            agent=self.agent,
            description="Assigned",
            phone_number="1",
            email="mine@example.com",
        )
        self.other = Lead.objects.create(
            first_name="Other",
            last_name="Lead",
            age=31,
            organisation=self.organisation,
            description="Unassigned",
            phone_number="2",
            email="other@example.com",
        )

    def test_agent_home_shows_only_assigned_leads(self):
        self.client.login(username="worker", password="pass12345")
        response = self.client.get(reverse("agent_home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mine Lead")
        self.assertNotContains(response, "Other Lead")
        self.assertEqual(response.context["lead_count"], 1)
        self.assertEqual(response.context["follow_up_count"], 1)

    def test_agent_can_update_stage_from_dashboard(self):
        self.client.login(username="worker", password="pass12345")
        response = self.client.post(
            reverse("agent_home"),
            {"lead_id": self.mine.pk, "category_id": self.category.pk},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("agent_home"))
        self.mine.refresh_from_db()
        self.assertEqual(self.mine.category_id, self.category.pk)
