from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from email_engine.campaigns import _finalize_if_done
from email_engine.models import Campaign, CampaignRecipient, EmailTemplate
from leads.assignment import assign_lead_to_agent
from leads.models import Agent, ContactList, Lead, Membership, Organisation
from notifications.models import Notification

User = get_user_model()


class NotificationCenterTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="notify_owner",
            password="pass12345",
            email="owner@example.com",
            is_organisor=True,
        )
        self.organisation = Organisation.objects.get(owner=self.owner)
        self.agent_user = User.objects.create_user(
            username="notify_agent",
            password="pass12345",
            email="agent@example.com",
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
        self.other_owner = User.objects.create_user(
            username="other_notify_owner",
            password="pass12345",
            is_organisor=True,
        )
        self.other_org = Organisation.objects.get(owner=self.other_owner)

    def test_assignment_notifies_agent(self):
        lead = Lead.objects.create(
            first_name="Ada",
            last_name="Lovelace",
            age=30,
            organisation=self.organisation,
            description="assign",
            phone_number="1",
            email="ada@example.com",
        )
        assign_lead_to_agent(lead, self.agent, actor=self.owner)
        note = Notification.objects.get(
            recipient=self.agent_user,
            kind=Notification.Kind.ASSIGNMENT,
        )
        self.assertEqual(note.organisation_id, self.organisation.pk)
        self.assertIn("Ada", note.title)
        self.assertFalse(note.is_read)

    def test_campaign_complete_notifies_organiser(self):
        template = EmailTemplate.objects.create(
            organisation=self.organisation,
            name="Blast",
            subject="Hi",
            body_html="<p>Hi</p>",
            body_text="Hi",
        )
        contact_list = ContactList.objects.create(
            organisation=self.organisation,
            name="Prospects",
            kind=ContactList.Kind.STATIC,
        )
        campaign = Campaign.objects.create(
            organisation=self.organisation,
            name="Spring blast",
            status=Campaign.Status.SENDING,
            created_by=self.owner,
            template=template,
            contact_list=contact_list,
        )
        lead = Lead.objects.create(
            first_name="R",
            last_name="One",
            age=25,
            organisation=self.organisation,
            description="r",
            phone_number="2",
            email="r1@example.com",
        )
        CampaignRecipient.objects.create(
            campaign=campaign,
            lead=lead,
            status=CampaignRecipient.Status.SENT,
        )
        _finalize_if_done(campaign)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, Campaign.Status.SENT)
        notes = Notification.objects.filter(
            organisation=self.organisation,
            kind=Notification.Kind.CAMPAIGN,
            recipient=self.owner,
        )
        self.assertEqual(notes.count(), 1)
        self.assertIn("Spring blast", notes.get().title)

        # Idempotent — already SENT should not duplicate
        _finalize_if_done(campaign)
        self.assertEqual(notes.count(), 1)

    def test_notifications_are_org_and_user_scoped(self):
        Notification.objects.create(
            organisation=self.organisation,
            recipient=self.owner,
            kind=Notification.Kind.BILLING,
            title="Ours",
        )
        Notification.objects.create(
            organisation=self.other_org,
            recipient=self.other_owner,
            kind=Notification.Kind.BILLING,
            title="Theirs",
        )
        Notification.objects.create(
            organisation=self.organisation,
            recipient=self.agent_user,
            kind=Notification.Kind.ASSIGNMENT,
            title="Agent only",
        )

        self.client.login(username="notify_owner", password="pass12345")
        response = self.client.get(reverse("app_notifications"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ours")
        self.assertNotContains(response, "Theirs")
        self.assertNotContains(response, "Agent only")

        self.client.login(username="notify_agent", password="pass12345")
        agent_inbox = self.client.get(reverse("agent_notifications"))
        self.assertEqual(agent_inbox.status_code, 200)
        self.assertContains(agent_inbox, "Agent only")
        self.assertNotContains(agent_inbox, "Ours")

    def test_mark_read_and_mark_all(self):
        n1 = Notification.objects.create(
            organisation=self.organisation,
            recipient=self.owner,
            kind=Notification.Kind.INVITE,
            title="One",
        )
        n2 = Notification.objects.create(
            organisation=self.organisation,
            recipient=self.owner,
            kind=Notification.Kind.BILLING,
            title="Two",
        )
        self.client.login(username="notify_owner", password="pass12345")
        response = self.client.post(
            reverse("app_notifications"),
            {"action": "mark_read", "notification_id": n1.pk},
        )
        self.assertEqual(response.status_code, 302)
        n1.refresh_from_db()
        self.assertTrue(n1.is_read)
        n2.refresh_from_db()
        self.assertFalse(n2.is_read)

        response = self.client.post(
            reverse("app_notifications"),
            {"action": "mark_all_read"},
        )
        self.assertEqual(response.status_code, 302)
        n2.refresh_from_db()
        self.assertTrue(n2.is_read)
