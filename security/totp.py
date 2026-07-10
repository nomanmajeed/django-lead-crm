"""TOTP helpers for optional owner 2FA."""

from __future__ import annotations

import pyotp


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(*, secret: str, user) -> str:
    issuer = "Lead CRM"
    return pyotp.TOTP(secret).provisioning_uri(
        name=user.email or user.username,
        issuer_name=issuer,
    )


def verify_totp(secret: str, code: str) -> bool:
    if not secret or not code:
        return False
    normalized = "".join(str(code).split())
    return pyotp.TOTP(secret).verify(normalized, valid_window=1)
