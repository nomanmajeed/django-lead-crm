from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from audit.models import AuditEntry
from audit.service import log_event
from email_engine.models import Campaign, EmailTemplate
from leads.assignment import assign_lead_to_agent
from leads.models import Agent, ContactList, Lead, Membership, Organisation

User = get_user_model()


class AuditLogTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="audit_owner",
            password="pass12345",
            email="audit@example.com",
            is_organisor=True,
        )
        self.organisation = Organisation.objects.get(owner=self.owner)
        self.agent_user = User.objects.create_user(
            username="audit_agent",
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

    def test_lead_and_assignment_changes_logged(self):
        self.client.login(username="audit_owner", password="pass12345")
        response = self.client.post(
            reverse("leads:lead_create"),
            {
                "first_name": "Ada",
                "last_name": "Lovelace",
                "age": 30,
                "description": "x",
                "phone_number": "1",
                "email": "ada-audit@example.com",
                "agent": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        lead = Lead.objects.get(email="ada-audit@example.com")
        self.assertTrue(
            AuditEntry.objects.filter(
                organisation=self.organisation,
                action="lead.created",
                object_id=lead.pk,
            ).exists()
        )

        assign_lead_to_agent(lead, self.agent, actor=self.owner)
        self.assertTrue(
            AuditEntry.objects.filter(
                action="lead.assigned",
                object_type=AuditEntry.ObjectType.LEAD,
                actor=self.owner,
            ).exists()
        )

    def test_campaign_and_team_changes_logged(self):
        template = EmailTemplate.objects.create(
            organisation=self.organisation,
            name="T",
            subject="Hi",
            body_html="<p>Hi</p>",
            body_text="Hi",
        )
        contact_list = ContactList.objects.create(
            organisation=self.organisation,
            name="List",
            kind=ContactList.Kind.STATIC,
        )
        self.client.login(username="audit_owner", password="pass12345")
        response = self.client.post(
            reverse("campaign_create"),
            {
                "name": "Audit blast",
                "contact_list": contact_list.pk,
                "template": template.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        campaign = Campaign.objects.get(name="Audit blast")
        self.assertTrue(
            AuditEntry.objects.filter(
                action="campaign.created", object_id=campaign.pk
            ).exists()
        )

        response = self.client.post(
            reverse("team_invite_create"),
            {"email": "newhire@example.com", "role": Membership.Role.AGENT},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            AuditEntry.objects.filter(
                organisation=self.organisation,
                action="team.invite_created",
                object_type=AuditEntry.ObjectType.TEAM,
            ).exists()
        )

    def test_filter_and_append_only(self):
        entry = log_event(
            organisation=self.organisation,
            actor=self.owner,
            action="lead.updated",
            object_type=AuditEntry.ObjectType.LEAD,
            object_id=1,
            object_repr="Test",
            summary="Updated lead",
        )
        with self.assertRaises(ValueError):
            entry.summary = "tampered"
            entry.save()
        with self.assertRaises(ValueError):
            entry.delete()

        self.client.login(username="audit_owner", password="pass12345")
        response = self.client.get(
            reverse("audit_log"),
            {"object_type": "lead", "actor": self.owner.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Updated lead")
        self.assertContains(response, "Filter")

    def test_export_gated_to_business(self):
        log_event(
            organisation=self.organisation,
            actor=self.owner,
            action="team.invite_created",
            object_type=AuditEntry.ObjectType.TEAM,
            summary="Invited someone",
        )
        self.client.login(username="audit_owner", password="pass12345")
        blocked = self.client.get(reverse("audit_export"))
        self.assertEqual(blocked.status_code, 403)
        self.assertContains(blocked, "Upgrade", status_code=403)

        self.organisation.plan = Organisation.Plan.BUSINESS
        self.organisation.save(update_fields=["plan"])
        allowed = self.client.get(reverse("audit_export"))
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed["Content-Type"], "text/csv")
        self.assertIn(b"Invited someone", allowed.content)
