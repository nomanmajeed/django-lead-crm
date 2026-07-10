from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

import pyotp

from security.rate_limit import is_allowed, increment
from security.totp import generate_totp_secret, verify_totp

User = get_user_model()


class RateLimitHelperTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_increment_blocks_after_limit(self):
        ip = "203.0.113.10"
        bucket = "test:bucket"
        self.assertTrue(is_allowed(bucket, ip, limit=2, window=60))
        increment(bucket, ip, window=60)
        self.assertTrue(is_allowed(bucket, ip, limit=2, window=60))
        increment(bucket, ip, window=60)
        self.assertFalse(is_allowed(bucket, ip, limit=2, window=60))


@override_settings(
    AUTH_LOGIN_RATE_LIMIT=2,
    AUTH_LOGIN_RATE_WINDOW=3600,
)
class AuthRateLimitMiddlewareTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="rate_user",
            password="pass12345",
            is_organisor=True,
        )

    def test_login_rate_limited_by_ip(self):
        payload = {"username": "rate_user", "password": "wrong"}
        for _ in range(2):
            response = self.client.post(reverse("login"), payload)
            self.assertNotEqual(response.status_code, 429)
        response = self.client.post(reverse("login"), payload)
        self.assertEqual(response.status_code, 429)


class TOTPTests(TestCase):
    def test_verify_valid_code(self):
        secret = generate_totp_secret()
        code = pyotp.TOTP(secret).now()
        self.assertTrue(verify_totp(secret, code))

    def test_verify_rejects_invalid_code(self):
        secret = generate_totp_secret()
        self.assertFalse(verify_totp(secret, "000000"))


class TwoFactorLoginTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner2fa",
            password="pass12345",
            is_organisor=True,
        )
        self.secret = generate_totp_secret()
        self.owner.totp_secret = self.secret
        self.owner.totp_enabled = True
        self.owner.save(update_fields=["totp_secret", "totp_enabled"])

    def test_login_with_2fa_requires_verification_step(self):
        response = self.client.post(
            reverse("login"),
            {"username": "owner2fa", "password": "pass12345"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("two_factor_verify"))

    def test_two_factor_verify_completes_login(self):
        self.client.post(
            reverse("login"),
            {"username": "owner2fa", "password": "pass12345"},
        )
        code = pyotp.TOTP(self.secret).now()
        response = self.client.post(
            reverse("two_factor_verify"),
            {"code": code},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("app_home"))


class SecurityHeadersTests(TestCase):
    def test_csp_header_present(self):
        response = self.client.get(reverse("landing_page"))
        self.assertIn("Content-Security-Policy", response.headers)
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
