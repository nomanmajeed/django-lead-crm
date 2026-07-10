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


class StripeBillingTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="stripe_owner",
            password="pass12345",
            email="stripe@example.com",
            is_organisor=True,
        )
        self.organisation = Organisation.objects.get(owner=self.owner)

    def test_simulate_upgrade_changes_plan(self):
        self.client.login(username="stripe_owner", password="pass12345")
        response = self.client.post(
            reverse("billing_plans"),
            {"action": "change_plan", "plan": "pro"},
        )
        self.assertEqual(response.status_code, 302)
        self.organisation.refresh_from_db()
        self.assertEqual(self.organisation.plan, Organisation.Plan.PRO)
        # Sequences unlock after upgrade
        seq = self.client.get(reverse("sequence_index"))
        self.assertEqual(seq.status_code, 200)

    def test_webhook_checkout_completed_updates_plan(self):
        from billing.stripe_service import handle_stripe_event

        event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "client_reference_id": str(self.organisation.pk),
                    "customer": "cus_test_123",
                    "subscription": "sub_test_123",
                    "metadata": {
                        "organisation_id": str(self.organisation.pk),
                        "plan": "pro",
                    },
                }
            },
        }
        result = handle_stripe_event(event)
        self.assertEqual(result, "checkout:pro")
        self.organisation.refresh_from_db()
        self.assertEqual(self.organisation.plan, Organisation.Plan.PRO)
        self.assertEqual(self.organisation.stripe_customer_id, "cus_test_123")
        self.assertEqual(self.organisation.stripe_subscription_id, "sub_test_123")

    def test_webhook_subscription_deleted_downgrades(self):
        from billing.stripe_service import handle_stripe_event

        self.organisation.plan = Organisation.Plan.BUSINESS
        self.organisation.stripe_customer_id = "cus_biz"
        self.organisation.stripe_subscription_id = "sub_biz"
        self.organisation.save()

        event = {
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "customer": "cus_biz",
                    "id": "sub_biz",
                    "metadata": {"organisation_id": str(self.organisation.pk)},
                }
            },
        }
        self.assertEqual(handle_stripe_event(event), "subscription:deleted")
        self.organisation.refresh_from_db()
        self.assertEqual(self.organisation.plan, Organisation.Plan.FREE)
        self.assertEqual(self.organisation.stripe_subscription_id, "")

    def test_webhook_rejects_bad_signature(self):
        from django.test import override_settings

        with override_settings(
            STRIPE_SECRET_KEY="sk_test_x",
            STRIPE_WEBHOOK_SECRET="whsec_test",
        ):
            response = self.client.post(
                reverse("stripe_webhook"),
                data=b'{"type":"ping"}',
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="t=1,v1=bad",
            )
        self.assertIn(response.status_code, {400, 403})

    def test_checkout_session_created_when_stripe_configured(self):
        from unittest.mock import MagicMock, patch

        from django.test import override_settings

        self.client.login(username="stripe_owner", password="pass12345")
        fake_session = {"url": "https://checkout.stripe.test/session", "id": "cs_test"}

        with override_settings(
            STRIPE_SECRET_KEY="sk_test_x",
            STRIPE_PRICE_PRO="price_pro_test",
            STRIPE_PRICE_BUSINESS="price_biz_test",
            STRIPE_BILLING_SIMULATE=False,
        ):
            with patch("billing.stripe_service._stripe") as mock_stripe_mod:
                stripe_api = MagicMock()
                stripe_api.Customer.create.return_value = {"id": "cus_new"}
                stripe_api.checkout.Session.create.return_value = fake_session
                mock_stripe_mod.return_value = stripe_api

                response = self.client.post(
                    reverse("billing_plans"),
                    {"action": "change_plan", "plan": "pro"},
                )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://checkout.stripe.test/session")
        self.organisation.refresh_from_db()
        self.assertEqual(self.organisation.stripe_customer_id, "cus_new")
