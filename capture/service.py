"""Public capture submit helpers: rate limits, validation, lead creation."""

from __future__ import annotations

import hashlib

from django import forms
from django.conf import settings
from django.core.cache import cache

from capture.models import LeadCaptureForm, default_fields_config
from leads.models import Lead

HONEYPOT_FIELD = "company_url"


def _rate_limit() -> int:
    return getattr(settings, "CAPTURE_FORM_RATE_LIMIT", 20)


def _rate_window() -> int:
    return getattr(settings, "CAPTURE_FORM_RATE_WINDOW", 3600)


def _rate_limit_key(form: LeadCaptureForm, ip: str) -> str:
    digest = hashlib.sha256(ip.encode("utf-8")).hexdigest()[:16]
    return f"capture:rate:{form.public_key}:{digest}"


def check_rate_limit(form: LeadCaptureForm, ip: str) -> bool:
    if not ip:
        return True
    key = _rate_limit_key(form, ip)
    return cache.get(key, 0) < _rate_limit()


def increment_rate_limit(form: LeadCaptureForm, ip: str) -> None:
    if not ip:
        return
    key = _rate_limit_key(form, ip)
    count = cache.get(key, 0) + 1
    cache.set(key, count, _rate_window())


class DynamicCaptureForm(forms.Form):
    company_url = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, capture_form: LeadCaptureForm, *args, **kwargs):
        self.capture_form = capture_form
        super().__init__(*args, **kwargs)
        config = capture_form.fields_config or default_fields_config()
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "last_name": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "email": forms.EmailInput(attrs={"class": "input input-bordered w-full"}),
            "phone_number": forms.TextInput(
                attrs={"class": "input input-bordered w-full"}
            ),
            "description": forms.Textarea(
                attrs={"class": "textarea textarea-bordered w-full", "rows": 3}
            ),
            "age": forms.NumberInput(attrs={"class": "input input-bordered w-full"}),
        }
        field_types = {
            "first_name": forms.CharField,
            "last_name": forms.CharField,
            "email": forms.EmailField,
            "phone_number": forms.CharField,
            "description": forms.CharField,
            "age": forms.IntegerField,
        }
        for name, field_cls in field_types.items():
            cfg = config.get(name, {})
            if not cfg.get("enabled", False):
                continue
            required = cfg.get("required", False)
            kwargs_field = {"required": required, "widget": widgets.get(name)}
            if name == "description":
                kwargs_field["required"] = required
            if name == "age":
                kwargs_field["min_value"] = 0
            self.fields[name] = field_cls(**kwargs_field)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get(HONEYPOT_FIELD):
            raise forms.ValidationError("Submission rejected.")
        return cleaned


def create_lead_from_capture(capture_form: LeadCaptureForm, cleaned_data: dict):
    lead = Lead.objects.create(
        organisation=capture_form.organisation,
        first_name=(cleaned_data.get("first_name") or "").strip(),
        last_name=(cleaned_data.get("last_name") or "").strip(),
        email=(cleaned_data.get("email") or "").strip(),
        phone_number=(cleaned_data.get("phone_number") or "").strip(),
        description=(cleaned_data.get("description") or "").strip()
        or f"Captured via {capture_form.name}",
        age=int(cleaned_data.get("age") or 0),
    )

    from leads.assignment import maybe_auto_assign

    maybe_auto_assign(lead)

    if capture_form.auto_sequence_id:
        from email_engine.sequences import enroll_lead

        try:
            enroll_lead(capture_form.auto_sequence, lead)
        except Exception:
            pass

    return lead
