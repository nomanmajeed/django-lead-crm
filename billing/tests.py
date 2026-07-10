from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from billing.entitlements import (
    EntitlementDenied,
    get_entitlements,
    has_feature,
    require_feature,
    require_within_limit,
)
from leads.models import Organisation

User = get_user_model()


class PlansEntitlementsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="plan_owner",
            password="pass12345",
            is_organisor=True,
        )
        self.organisation = Organisation.objects.get(owner=self.owner)
        self.assertEqual(self.organisation.plan, Organisation.Plan.FREE)

    def test_free_plan_limits_readable(self):
        entitlements = get_entitlements(self.organisation)
        self.assertEqual(entitlements.key, "free")
        self.assertEqual(entitlements.seats, 2)
        self.assertEqual(entitlements.leads, 100)
        self.assertEqual(entitlements.monthly_emails, 200)
        self.assertFalse(entitlements.has_feature("sequences"))
        self.assertTrue(entitlements.has_feature("campaigns"))

    def test_free_org_blocked_from_sequences_with_upgrade_cta(self):
        self.client.login(username="plan_owner", password="pass12345")
        response = self.client.get(reverse("sequence_index"))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Upgrade to unlock", status_code=403)
        self.assertContains(response, "View plans", status_code=403)
        self.assertContains(response, "sequences", status_code=403)

        create = self.client.get(reverse("sequence_create"))
        self.assertEqual(create.status_code, 403)

    def test_pro_org_can_open_sequences(self):
        self.organisation.plan = Organisation.Plan.PRO
        self.organisation.save(update_fields=["plan"])
        self.assertTrue(has_feature(self.organisation, "sequences"))
        self.client.login(username="plan_owner", password="pass12345")
        response = self.client.get(reverse("sequence_index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sequences")

    def test_require_feature_and_limit_helpers(self):
        with self.assertRaises(EntitlementDenied) as ctx:
            require_feature(self.organisation, "sequences")
        self.assertTrue(ctx.exception.upgrade_required)

        self.organisation.plan = Organisation.Plan.PRO
        self.organisation.save(update_fields=["plan"])
        require_feature(self.organisation, "sequences")

        # Pro allows 20 sequences — at cap should deny
        with self.assertRaises(EntitlementDenied):
            require_within_limit(self.organisation, "sequences", 20)

        require_within_limit(self.organisation, "sequences", 19)

    def test_billing_page_shows_current_plan_limits(self):
        self.client.login(username="plan_owner", password="pass12345")
        response = self.client.get(reverse("billing_plans"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Free")
        self.assertContains(response, "Sequences")
        self.assertContains(response, "Not available on Free")
        self.assertEqual(response.context["entitlements"].key, "free")
