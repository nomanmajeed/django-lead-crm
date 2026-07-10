from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

User = get_user_model()


@override_settings(DJANGO_ADMIN_ENABLED=False)
class AdminDisabledTests(TestCase):
    def test_admin_returns_404_when_disabled(self):
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 404)


@override_settings(DJANGO_ADMIN_ENABLED=True)
class AdminGuardTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff_user",
            password="pass12345",
            is_staff=True,
            is_superuser=True,
        )
        self.regular = User.objects.create_user(
            username="regular_user",
            password="pass12345",
            is_staff=False,
        )

    def test_anonymous_admin_index_hidden(self):
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 404)

    def test_non_staff_forbidden_on_admin_index(self):
        self.client.login(username="regular_user", password="pass12345")
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 403)

    def test_staff_can_access_admin(self):
        self.client.login(username="staff_user", password="pass12345")
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)

    def test_admin_login_page_reachable_when_enabled(self):
        response = self.client.get("/admin/login/")
        self.assertEqual(response.status_code, 200)


class ObservabilitySettingsTests(TestCase):
    def test_structured_logging_configured(self):
        from django.conf import settings

        self.assertTrue(hasattr(settings, "LOGGING"))
        self.assertEqual(
            settings.LOGGING["formatters"]["structured"]["format"],
            "%(asctime)s level=%(levelname)s logger=%(name)s %(message)s",
        )

    @override_settings(
        SENTRY_DSN="https://example@o0.ingest.sentry.io/0",
        SENTRY_ENVIRONMENT="test",
    )
    def test_sentry_configure_does_not_raise(self):
        from djcrm.observability import configure_sentry

        configure_sentry(
            dsn="https://example@o0.ingest.sentry.io/0",
            environment="test",
        )
