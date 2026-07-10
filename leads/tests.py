from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from leads.models import (
    Agent,
    Category,
    ContactList,
    ContactListMembership,
    Invite,
    Lead,
    LeadActivity,
    LeadNote,
    LeadTask,
    Membership,
    Organisation,
)
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


class PipelineTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="pipe_owner",
            password="pass12345",
            is_organisor=True,
        )
        self.organisation = Organisation.objects.get(owner=self.owner)
        self.other_owner = User.objects.create_user(
            username="pipe_other",
            password="pass12345",
            is_organisor=True,
        )
        self.other_org = Organisation.objects.get(owner=self.other_owner)
        self.lead = Lead.objects.create(
            first_name="Pipe",
            last_name="Lead",
            age=25,
            organisation=self.organisation,
            description="In pipeline",
            phone_number="100",
            email="pipe@example.com",
        )
        Lead.objects.create(
            first_name="Secret",
            last_name="Lead",
            age=40,
            organisation=self.other_org,
            description="Other org",
            phone_number="200",
            email="secret@example.com",
        )

    def test_pipeline_seeds_stages_and_shows_org_leads(self):
        self.client.login(username="pipe_owner", password="pass12345")
        response = self.client.get(reverse("leads:pipeline"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pipe Lead")
        self.assertNotContains(response, "Secret Lead")
        self.assertContains(response, "Qualified")
        self.assertTrue(
            Category.objects.for_org(self.organisation)
            .filter(name="New")
            .exists()
        )

    def test_pipeline_list_view_and_search_filter(self):
        self.client.login(username="pipe_owner", password="pass12345")
        response = self.client.get(
            reverse("leads:pipeline"), {"view": "list", "q": "Pipe"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["view_mode"], "list")
        self.assertContains(response, "Pipe Lead")
        response = self.client.get(
            reverse("leads:pipeline"), {"view": "list", "q": "zzzz"}
        )
        self.assertNotContains(response, "Pipe Lead")

    def test_pipeline_stage_move_stays_org_scoped(self):
        self.client.login(username="pipe_owner", password="pass12345")
        self.client.get(reverse("leads:pipeline"))
        won = Category.objects.for_org(self.organisation).get(name="Won")
        response = self.client.post(
            reverse("leads:pipeline"),
            {"lead_id": self.lead.pk, "category_id": won.pk},
        )
        self.assertEqual(response.status_code, 302)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.category_id, won.pk)

        # Cannot move another org's lead
        foreign = Lead.objects.get(email="secret@example.com")
        response = self.client.post(
            reverse("leads:pipeline"),
            {"lead_id": foreign.pk, "category_id": won.pk},
        )
        self.assertEqual(response.status_code, 404)


class LeadDetail360Tests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="detail_owner",
            password="pass12345",
            is_organisor=True,
        )
        self.organisation = Organisation.objects.get(owner=self.owner)
        self.agent_user = User.objects.create_user(
            username="detail_agent",
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
        self.lead = Lead.objects.create(
            first_name="Ada",
            last_name="Detail",
            age=33,
            organisation=self.organisation,
            agent=self.agent,
            description="360 lead",
            phone_number="555",
            email="ada@example.com",
        )

    def test_organiser_can_add_note_and_see_timeline(self):
        self.client.login(username="detail_owner", password="pass12345")
        response = self.client.post(
            reverse("leads:lead_detail", kwargs={"pk": self.lead.pk}),
            {"action": "add_note", "body": "Called the prospect"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            LeadNote.objects.filter(lead=self.lead, body="Called the prospect").exists()
        )
        self.assertTrue(
            LeadActivity.objects.filter(
                lead=self.lead, kind=LeadActivity.Kind.NOTE
            ).exists()
        )
        page = self.client.get(
            reverse("leads:lead_detail", kwargs={"pk": self.lead.pk})
        )
        self.assertContains(page, "Called the prospect")
        self.assertContains(page, "Timeline")

    def test_agent_can_create_and_complete_task(self):
        self.client.login(username="detail_agent", password="pass12345")
        url = reverse("agent_leads:lead_detail", kwargs={"pk": self.lead.pk})
        response = self.client.post(
            url, {"action": "add_task", "title": "Send proposal"}
        )
        self.assertEqual(response.status_code, 302)
        task = LeadTask.objects.get(lead=self.lead, title="Send proposal")
        self.assertIsNone(task.completed_at)

        response = self.client.post(
            url, {"action": "complete_task", "task_id": task.pk}
        )
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertIsNotNone(task.completed_at)
        self.assertTrue(
            LeadActivity.objects.filter(
                lead=self.lead, kind=LeadActivity.Kind.TASK_COMPLETED
            ).exists()
        )


class LeadImportExportTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="io_owner",
            password="pass12345",
            is_organisor=True,
        )
        self.organisation = Organisation.objects.get(owner=self.owner)
        self.other = User.objects.create_user(
            username="io_other",
            password="pass12345",
            is_organisor=True,
        )
        self.other_org = Organisation.objects.get(owner=self.other)

    def test_import_100_rows_into_correct_org_and_skips_bad_rows(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        lines = ["first_name,last_name,email,phone_number,age,description"]
        for i in range(100):
            lines.append(
                f"First{i},Last{i},user{i}@example.com,555{i:04d},30,Imported {i}"
            )
        lines.append(",,,,not-an-age,")  # bad row — missing required + bad age
        csv_bytes = ("\n".join(lines) + "\n").encode("utf-8")
        upload = SimpleUploadedFile("leads.csv", csv_bytes, content_type="text/csv")

        self.client.login(username="io_owner", password="pass12345")
        response = self.client.post(
            reverse("leads:lead_import"),
            {"action": "upload", "csv_file": upload},
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.post(
            reverse("leads:lead_import"),
            {
                "action": "import",
                "map_first_name": "first_name",
                "map_last_name": "last_name",
                "map_email": "email",
                "map_phone_number": "phone_number",
                "map_age": "age",
                "map_description": "description",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Lead.objects.for_org(self.organisation).count(), 100
        )
        self.assertEqual(Lead.objects.for_org(self.other_org).count(), 0)
        self.assertContains(response, "100 leads imported")
        self.assertContains(response, "1 row skipped")

    def test_export_matches_pipeline_filters(self):
        Lead.objects.create(
            first_name="Keep",
            last_name="Me",
            age=20,
            organisation=self.organisation,
            description="match",
            phone_number="1",
            email="keep@example.com",
        )
        Lead.objects.create(
            first_name="Drop",
            last_name="Me",
            age=21,
            organisation=self.organisation,
            description="other",
            phone_number="2",
            email="drop@example.com",
        )
        self.client.login(username="io_owner", password="pass12345")
        response = self.client.get(
            reverse("leads:lead_export"), {"q": "keep@example.com"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        body = response.content.decode("utf-8")
        self.assertIn("keep@example.com", body)
        self.assertNotIn("drop@example.com", body)


class AssignmentRulesTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="assign_owner",
            password="pass12345",
            is_organisor=True,
        )
        self.organisation = Organisation.objects.get(owner=self.owner)
        self.agents = []
        for name in ("agent_a", "agent_b", "agent_c"):
            user = User.objects.create_user(
                username=name,
                password="pass12345",
                is_organisor=False,
                is_agent=True,
            )
            agent = Agent.objects.create(user=user, organisation=self.organisation)
            Membership.objects.create(
                user=user,
                organisation=self.organisation,
                role=Membership.Role.AGENT,
            )
            self.agents.append(agent)

    def test_auto_assign_round_robin_on_create(self):
        self.organisation.auto_assign_enabled = True
        self.organisation.save(update_fields=["auto_assign_enabled"])
        self.client.login(username="assign_owner", password="pass12345")

        assigned = []
        for i in range(6):
            response = self.client.post(
                reverse("leads:lead_create"),
                {
                    "first_name": f"L{i}",
                    "last_name": "Auto",
                    "age": 20,
                    "description": "rr",
                    "phone_number": f"100{i}",
                    "email": f"l{i}@example.com",
                    "agent": "",
                },
            )
            self.assertEqual(response.status_code, 302)
            lead = Lead.objects.get(email=f"l{i}@example.com")
            self.assertIsNotNone(lead.agent_id)
            assigned.append(lead.agent_id)

        # Fair rotation across the three agents
        self.assertEqual(assigned.count(self.agents[0].pk), 2)
        self.assertEqual(assigned.count(self.agents[1].pk), 2)
        self.assertEqual(assigned.count(self.agents[2].pk), 2)

    def test_manual_assign_overrides_and_disabled_stays_unassigned(self):
        self.organisation.auto_assign_enabled = False
        self.organisation.save(update_fields=["auto_assign_enabled"])
        lead = Lead.objects.create(
            first_name="Solo",
            last_name="Lead",
            age=22,
            organisation=self.organisation,
            description="manual",
            phone_number="9",
            email="solo@example.com",
        )
        self.assertIsNone(lead.agent_id)

        self.client.login(username="assign_owner", password="pass12345")
        response = self.client.post(
            reverse("leads:assign_agent", kwargs={"pk": lead.pk}),
            {"agent": self.agents[1].pk},
        )
        self.assertEqual(response.status_code, 302)
        lead.refresh_from_db()
        self.assertEqual(lead.agent_id, self.agents[1].pk)

    def test_assignment_settings_toggle(self):
        self.client.login(username="assign_owner", password="pass12345")
        response = self.client.post(
            reverse("assignment_settings"),
            {"auto_assign_enabled": "on"},
        )
        self.assertEqual(response.status_code, 302)
        self.organisation.refresh_from_db()
        self.assertTrue(self.organisation.auto_assign_enabled)


class ContactListSegmentTests(TestCase):
    def setUp(self):
        from datetime import timedelta

        from django.utils import timezone

        self.owner = User.objects.create_user(
            username="list_owner",
            password="pass12345",
            is_organisor=True,
        )
        self.organisation = Organisation.objects.get(owner=self.owner)
        self.other = User.objects.create_user(
            username="list_other",
            password="pass12345",
            is_organisor=True,
        )
        self.other_org = Organisation.objects.get(owner=self.other)
        self.recent = Lead.objects.create(
            first_name="Recent",
            last_name="Lead",
            age=20,
            organisation=self.organisation,
            description="new",
            phone_number="1",
            email="recent@example.com",
        )
        self.old = Lead.objects.create(
            first_name="Old",
            last_name="Lead",
            age=40,
            organisation=self.organisation,
            description="old",
            phone_number="2",
            email="old@example.com",
        )
        Lead.objects.filter(pk=self.old.pk).update(
            date_added=timezone.now() - timedelta(days=30)
        )
        Lead.objects.create(
            first_name="Other",
            last_name="Org",
            age=25,
            organisation=self.other_org,
            description="x",
            phone_number="3",
            email="otherorg@example.com",
        )

    def test_new_leads_last_7_days_segment_and_org_scope(self):
        self.client.login(username="list_owner", password="pass12345")
        response = self.client.get(reverse("list_index"))
        self.assertEqual(response.status_code, 200)
        segment = ContactList.objects.for_org(self.organisation).get(
            name="New leads last 7 days"
        )
        self.assertEqual(segment.kind, ContactList.Kind.SEGMENT)
        detail = self.client.get(reverse("list_detail", kwargs={"pk": segment.pk}))
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.context["member_count"], 1)
        self.assertContains(detail, "Recent Lead")
        self.assertNotContains(detail, "Old Lead")
        self.assertNotContains(detail, "Other Org")

    def test_static_list_add_and_preview_count(self):
        self.client.login(username="list_owner", password="pass12345")
        response = self.client.post(
            reverse("list_create"),
            {"name": "VIP", "kind": "static"},
        )
        self.assertEqual(response.status_code, 302)
        contact_list = ContactList.objects.get(name="VIP")
        response = self.client.post(
            reverse("list_detail", kwargs={"pk": contact_list.pk}),
            {"action": "add", "lead_id": self.recent.pk},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ContactListMembership.objects.filter(
                contact_list=contact_list, lead=self.recent
            ).exists()
        )
        detail = self.client.get(reverse("list_detail", kwargs={"pk": contact_list.pk}))
        self.assertEqual(detail.context["member_count"], 1)


class SettingsHubTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="settings_owner",
            password="pass12345",
            email="settings@example.com",
            is_organisor=True,
        )
        self.organisation = Organisation.objects.get(owner=self.owner)
        self.admin_user = User.objects.create_user(
            username="settings_admin",
            password="pass12345",
            is_organisor=False,
            is_agent=False,
        )
        Membership.objects.create(
            user=self.admin_user,
            organisation=self.organisation,
            role=Membership.Role.ADMIN,
        )
        # Keep denormalized flag consistent with membership
        self.admin_user.is_organisor = True
        self.admin_user.save(update_fields=["is_organisor"])

    def test_profile_persists_and_applies_to_email_from(self):
        from email_engine.service import queue_transactional_email

        self.client.login(username="settings_owner", password="pass12345")
        response = self.client.post(
            reverse("settings_profile"),
            {
                "name": "Acme CRM",
                "timezone": "Asia/Karachi",
                "primary_color": "#124E77",
                "from_name": "Acme Sales",
                "from_email": "hello@acme.example",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.organisation.refresh_from_db()
        self.assertEqual(self.organisation.name, "Acme CRM")
        self.assertEqual(self.organisation.timezone, "Asia/Karachi")
        self.assertEqual(self.organisation.primary_color, "#124E77")
        self.assertEqual(
            self.organisation.resolve_from_email(),
            "Acme Sales <hello@acme.example>",
        )

        outbound = queue_transactional_email(
            to_email="lead@example.com",
            subject="Hi",
            body_text="Hi",
            organisation=self.organisation,
            async_send=False,
        )
        self.assertEqual(outbound.from_email, "Acme Sales <hello@acme.example>")

        hub = self.client.get(reverse("settings_hub"))
        self.assertEqual(hub.status_code, 200)
        self.assertContains(hub, "Organisation profile")
        self.assertContains(hub, "Danger zone")

    def test_danger_zone_owner_only_and_deletes_org(self):
        self.client.login(username="settings_admin", password="pass12345")
        blocked = self.client.get(reverse("settings_danger"))
        self.assertEqual(blocked.status_code, 302)
        self.assertEqual(blocked.url, reverse("settings_hub"))

        self.client.login(username="settings_owner", password="pass12345")
        bad = self.client.post(
            reverse("settings_danger"),
            {"confirm_name": "Wrong Name"},
        )
        self.assertEqual(bad.status_code, 200)
        self.assertTrue(Organisation.objects.filter(pk=self.organisation.pk).exists())

        ok = self.client.post(
            reverse("settings_danger"),
            {"confirm_name": self.organisation.name},
        )
        self.assertEqual(ok.status_code, 302)
        self.assertFalse(Organisation.objects.filter(pk=self.organisation.pk).exists())


class MarketingSiteTests(TestCase):
    def test_landing_uses_daisyui_and_signup_cta(self):
        response = self.client.get(reverse("landing_page"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lead CRM")
        self.assertContains(response, reverse("signup"))
        self.assertContains(response, 'data-theme="leadcrm"', html=False)

    def test_pricing_matches_free_pro_business(self):
        response = self.client.get(reverse("marketing_pricing"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Free")
        self.assertContains(response, "Pro")
        self.assertContains(response, "Business")
        self.assertContains(response, "100")  # free leads
        self.assertContains(response, "5000")  # pro leads
        self.assertContains(response, "Not included")  # free sequences
        self.assertContains(response, reverse("signup"))

    def test_features_and_signup_links(self):
        response = self.client.get(reverse("marketing_features"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pipeline")
        self.assertContains(response, reverse("signup"))
        signup = self.client.get(reverse("signup"))
        self.assertEqual(signup.status_code, 200)


class OnboardingChecklistTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="onboard_owner",
            password="pass12345",
            is_organisor=True,
        )
        self.organisation = Organisation.objects.get(owner=self.owner)

    def test_checklist_appears_for_new_org(self):
        self.client.login(username="onboard_owner", password="pass12345")
        response = self.client.get(reverse("app_home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Get started")
        self.assertContains(response, "Invite a teammate")
        self.assertContains(response, "Import leads")

    def test_items_complete_automatically(self):
        from email_engine.models import Campaign, EmailTemplate
        from leads.models import ContactList

        agent_user = User.objects.create_user(
            username="onboard_agent",
            password="pass12345",
            is_organisor=False,
            is_agent=True,
        )
        Membership.objects.create(
            user=agent_user,
            organisation=self.organisation,
            role=Membership.Role.AGENT,
        )
        Lead.objects.create(
            first_name="A",
            last_name="B",
            age=20,
            organisation=self.organisation,
            description="x",
            phone_number="1",
            email="ab@example.com",
        )
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
        Campaign.objects.create(
            organisation=self.organisation,
            name="Done",
            status=Campaign.Status.SENT,
            template=template,
            contact_list=contact_list,
            created_by=self.owner,
        )

        from leads.onboarding import onboarding_snapshot

        snap = onboarding_snapshot(self.organisation)
        self.assertTrue(snap["show"])
        self.assertEqual(snap["completed"], 3)
        self.assertTrue(snap["all_done"])

    def test_owner_can_dismiss_permanently(self):
        self.client.login(username="onboard_owner", password="pass12345")
        response = self.client.post(reverse("onboarding_dismiss"))
        self.assertEqual(response.status_code, 302)
        self.organisation.refresh_from_db()
        self.assertIsNotNone(self.organisation.onboarding_dismissed_at)

        dashboard = self.client.get(reverse("app_home"))
        self.assertNotContains(dashboard, "Get started")
