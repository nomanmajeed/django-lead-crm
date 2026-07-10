"""Organiser CRUD for reusable email templates with merge tags."""

from html import escape

from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from agents.mixins import OrganisorAndLoginRequiredMixin
from email_engine.merge import (
    SUPPORTED_MERGE_TAGS,
    build_merge_context,
    render_merge,
)
from email_engine.models import EmailTemplate, OutboundEmail
from email_engine.service import queue_transactional_email
from leads.models import Lead


def _safe_preview_html(body_html: str, context: dict) -> str:
    """Escape merge values, leave organiser-authored HTML structure intact."""
    safe_context = {key: escape(str(value)) for key, value in context.items()}
    return render_merge(body_html, safe_context, escape_html=False)


class EmailTemplateForm(forms.ModelForm):
    class Meta:
        model = EmailTemplate
        fields = ("name", "subject", "body_html", "body_text")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name in {"body_html", "body_text"}:
                field.widget = forms.Textarea(
                    attrs={
                        "class": "textarea textarea-bordered w-full font-mono text-sm",
                        "rows": 8,
                    }
                )
            else:
                field.widget.attrs.setdefault(
                    "class", "input input-bordered input-sm w-full"
                )


class EmailTemplateIndexView(OrganisorAndLoginRequiredMixin, View):
    def get(self, request):
        templates = EmailTemplate.objects.filter(
            organisation=request.organisation
        ).order_by("name")
        return render(
            request,
            "app/email_templates/index.html",
            {"topbar_title": "Email templates", "templates": templates},
        )


class EmailTemplateCreateView(OrganisorAndLoginRequiredMixin, View):
    def get(self, request):
        return render(
            request,
            "app/email_templates/form.html",
            {
                "topbar_title": "New template",
                "form": EmailTemplateForm(
                    initial={
                        "subject": "Hello {{first_name}}",
                        "body_html": (
                            '<div class="space-y-3" style="font-family:system-ui,sans-serif;line-height:1.5">'
                            "<p>Hi {{first_name}},</p>"
                            "<p>Thanks for connecting with {{organisation_name}}.</p>"
                            "<p>— The team</p>"
                            "</div>"
                        ),
                        "body_text": (
                            "Hi {{first_name}},\n\n"
                            "Thanks for connecting with {{organisation_name}}.\n"
                        ),
                    }
                ),
                "heading": "Create email template",
                "merge_tags": SUPPORTED_MERGE_TAGS,
                "merge_tag_examples": [f"{{{{{tag}}}}}" for tag in SUPPORTED_MERGE_TAGS],
            },
        )

    def post(self, request):
        form = EmailTemplateForm(request.POST)
        if form.is_valid():
            template = form.save(commit=False)
            template.organisation = request.organisation
            template.save()
            messages.success(request, f"Saved template “{template.name}”.")
            return redirect("email_template_detail", pk=template.pk)
        return render(
            request,
            "app/email_templates/form.html",
            {
                "topbar_title": "New template",
                "form": form,
                "heading": "Create email template",
                "merge_tags": SUPPORTED_MERGE_TAGS,
                "merge_tag_examples": [f"{{{{{tag}}}}}" for tag in SUPPORTED_MERGE_TAGS],
            },
        )


class EmailTemplateDetailView(OrganisorAndLoginRequiredMixin, View):
    def _get(self, request, pk):
        return get_object_or_404(
            EmailTemplate, pk=pk, organisation=request.organisation
        )

    def _preview_payload(self, request, template):
        sample_lead = (
            Lead.objects.for_org(request.organisation)
            .order_by("-date_added")
            .first()
        )
        context = build_merge_context(
            lead=sample_lead,
            organisation=request.organisation,
            user=request.user,
        )
        return {
            "preview_subject": render_merge(template.subject, context),
            "preview_html": _safe_preview_html(template.body_html, context),
            "preview_text": render_merge(template.body_text, context),
            "preview_context": context,
            "sample_lead": sample_lead,
        }

    def get(self, request, pk):
        template = self._get(request, pk)
        payload = self._preview_payload(request, template)
        return render(
            request,
            "app/email_templates/detail.html",
            {
                "topbar_title": template.name,
                "template": template,
                "form": EmailTemplateForm(instance=template),
                "merge_tags": SUPPORTED_MERGE_TAGS,
                "merge_tag_examples": [f"{{{{{tag}}}}}" for tag in SUPPORTED_MERGE_TAGS],
                **payload,
            },
        )

    def post(self, request, pk):
        template = self._get(request, pk)
        action = request.POST.get("action", "save")

        if action == "test_send":
            to_email = (request.user.email or "").strip()
            if not to_email:
                messages.error(
                    request,
                    "Add an email address to your user account to send a test.",
                )
                return redirect("email_template_detail", pk=pk)
            sample_lead = (
                Lead.objects.for_org(request.organisation)
                .order_by("-date_added")
                .first()
            )
            context = build_merge_context(
                lead=sample_lead,
                organisation=request.organisation,
                user=request.user,
            )
            outbound = queue_transactional_email(
                to_email=to_email,
                subject=render_merge(template.subject, context),
                body_text=render_merge(
                    template.body_text or template.body_html, context
                ),
                body_html=render_merge(template.body_html, context),
                organisation=request.organisation,
            )
            outbound.refresh_from_db()
            if outbound.status == OutboundEmail.Status.SENT:
                messages.success(request, f"Test email sent to {to_email}.")
            elif outbound.status == OutboundEmail.Status.QUEUED:
                messages.success(request, f"Test email queued for {to_email}.")
            else:
                messages.error(
                    request, outbound.error_message or "Test send failed."
                )
            return redirect("email_template_detail", pk=pk)

        if action == "delete":
            name = template.name
            template.delete()
            messages.success(request, f"Deleted “{name}”.")
            return redirect("email_template_index")

        form = EmailTemplateForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
            messages.success(request, "Template updated.")
            return redirect("email_template_detail", pk=pk)

        payload = self._preview_payload(request, template)
        return render(
            request,
            "app/email_templates/detail.html",
            {
                "topbar_title": template.name,
                "template": template,
                "form": form,
                "merge_tags": SUPPORTED_MERGE_TAGS,
                "merge_tag_examples": [f"{{{{{tag}}}}}" for tag in SUPPORTED_MERGE_TAGS],
                **payload,
            },
        )
