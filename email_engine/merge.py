"""Merge-tag rendering for email templates ({{first_name}}, etc.)."""

from __future__ import annotations

import re
from html import escape

MERGE_TAG_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")

SUPPORTED_MERGE_TAGS = (
    "first_name",
    "last_name",
    "email",
    "phone_number",
    "company",
    "organisation_name",
    "full_name",
)


def build_merge_context(lead=None, organisation=None, user=None) -> dict:
    """Build a flat merge context from a lead / org / user."""
    custom = {}
    if lead is not None:
        custom = lead.custom_fields or {}
    org = organisation
    if org is None and lead is not None:
        org = lead.organisation

    first = getattr(lead, "first_name", "") or (user.first_name if user else "") or ""
    last = getattr(lead, "last_name", "") or (user.last_name if user else "") or ""
    email = getattr(lead, "email", "") or (user.email if user else "") or ""
    phone = getattr(lead, "phone_number", "") or ""
    company = custom.get("company", "") or (org.name if org else "")
    org_name = org.name if org else ""

    if user and not first and not last:
        first = user.username

    return {
        "first_name": first,
        "last_name": last,
        "full_name": f"{first} {last}".strip() or email,
        "email": email,
        "phone_number": phone,
        "company": company,
        "organisation_name": org_name,
    }


def render_merge(template_str: str, context: dict, *, escape_html: bool = False) -> str:
    """Replace {{tag}} placeholders. Unknown tags become empty strings."""

    def repl(match):
        key = match.group(1)
        value = context.get(key, "")
        text = "" if value is None else str(value)
        return escape(text) if escape_html else text

    return MERGE_TAG_RE.sub(repl, template_str or "")
