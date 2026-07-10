"""Organiser UI for one-shot email campaigns."""

from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views import View

from agents.mixins import OrganisorAndLoginRequiredMixin
from email_engine.campaigns import (
    cancel_campaign,
    recipient_counts,
    schedule_or_send_campaign,
)
from email_engine.analytics import campaign_metrics
from email_engine.models import Campaign, EmailTemplate
from leads.lists import resolve_list_members
from leads.models import ContactList


class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ("name", "contact_list", "template")

    def __init__(self, *args, organisation=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organisation = organisation
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault(
                    "class", "select select-bordered select-sm w-full"
                )
            else:
                field.widget.attrs.setdefault(
                    "class", "input input-bordered input-sm w-full"
                )
        if organisation is not None:
            self.fields["contact_list"].queryset = ContactList.objects.for_org(
                organisation
            ).order_by("kind", "name")
            self.fields["template"].queryset = EmailTemplate.objects.filter(
                organisation=organisation
            ).order_by("name")

    def clean(self):
        cleaned = super().clean()
        contact_list = cleaned.get("contact_list")
        template = cleaned.get("template")
        if (
            self.organisation
            and contact_list
            and contact_list.organisation_id != self.organisation.pk
        ):
            self.add_error("contact_list", "List must belong to your organisation.")
        if (
            self.organisation
            and template
            and template.organisation_id != self.organisation.pk
        ):
            self.add_error("template", "Template must belong to your organisation.")
        return cleaned


class CampaignIndexView(OrganisorAndLoginRequiredMixin, View):
    def get(self, request):
        campaigns = (
            Campaign.objects.filter(organisation=request.organisation)
            .select_related("contact_list", "template")
            .order_by("-created_at")
        )
        return render(
            request,
            "app/campaigns/index.html",
            {"topbar_title": "Campaigns", "campaigns": campaigns},
        )


class CampaignCreateView(OrganisorAndLoginRequiredMixin, View):
    def get(self, request):
        return render(
            request,
            "app/campaigns/form.html",
            {
                "topbar_title": "New campaign",
                "form": CampaignForm(organisation=request.organisation),
                "heading": "Create campaign",
            },
        )

    def post(self, request):
        form = CampaignForm(request.POST, organisation=request.organisation)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.organisation = request.organisation
            campaign.created_by = request.user
            campaign.status = Campaign.Status.DRAFT
            campaign.save()
            from audit.service import log_campaign_change

            log_campaign_change(
                campaign,
                action="campaign.created",
                summary=f"Created campaign “{campaign.name}”",
                actor=request.user,
            )
            messages.success(request, f"Draft campaign “{campaign.name}” created.")
            return redirect("campaign_detail", pk=campaign.pk)
        return render(
            request,
            "app/campaigns/form.html",
            {
                "topbar_title": "New campaign",
                "form": form,
                "heading": "Create campaign",
            },
        )


class CampaignDetailView(OrganisorAndLoginRequiredMixin, View):
    def _get(self, request, pk):
        return get_object_or_404(
            Campaign.objects.select_related("contact_list", "template"),
            pk=pk,
            organisation=request.organisation,
        )

    def get(self, request, pk):
        campaign = self._get(request, pk)
        counts = recipient_counts(campaign)
        preview_count = resolve_list_members(campaign.contact_list).exclude(
            email=""
        ).count()
        recipients = (
            campaign.recipients.select_related("lead", "outbound_email").order_by(
                "pk"
            )[:100]
        )
        form = None
        if campaign.can_edit:
            form = CampaignForm(
                instance=campaign, organisation=request.organisation
            )
        return render(
            request,
            "app/campaigns/detail.html",
            {
                "topbar_title": campaign.name,
                "campaign": campaign,
                "form": form,
                "counts": counts,
                "preview_count": preview_count,
                "recipients": recipients,
                "metrics": campaign_metrics(campaign),
            },
        )

    def post(self, request, pk):
        campaign = self._get(request, pk)
        action = request.POST.get("action", "save")

        if action == "save" and campaign.can_edit:
            form = CampaignForm(
                request.POST,
                instance=campaign,
                organisation=request.organisation,
            )
            if form.is_valid():
                form.save()
                from audit.service import log_campaign_change

                log_campaign_change(
                    campaign,
                    action="campaign.updated",
                    summary=f"Updated campaign “{campaign.name}”",
                    actor=request.user,
                )
                messages.success(request, "Campaign updated.")
                return redirect("campaign_detail", pk=pk)
            counts = recipient_counts(campaign)
            preview_count = resolve_list_members(campaign.contact_list).exclude(
                email=""
            ).count()
            return render(
                request,
                "app/campaigns/detail.html",
                {
                    "topbar_title": campaign.name,
                    "campaign": campaign,
                    "form": form,
                    "counts": counts,
                    "preview_count": preview_count,
                    "recipients": campaign.recipients.select_related("lead")[:100],
                },
            )

        if action == "send_now" and campaign.can_send:
            try:
                schedule_or_send_campaign(campaign, send_now=True)
                messages.success(request, "Campaign sending started.")
            except ValueError as exc:
                messages.error(request, str(exc))
            return redirect("campaign_detail", pk=pk)

        if action == "schedule" and campaign.can_send:
            raw = (request.POST.get("scheduled_at") or "").strip()
            scheduled_at = parse_datetime(raw.replace("T", " "))
            if scheduled_at is None:
                messages.error(request, "Provide a valid schedule date/time.")
                return redirect("campaign_detail", pk=pk)
            if timezone.is_naive(scheduled_at):
                scheduled_at = timezone.make_aware(
                    scheduled_at, timezone.get_current_timezone()
                )
            if scheduled_at <= timezone.now():
                messages.error(request, "Schedule time must be in the future.")
                return redirect("campaign_detail", pk=pk)
            try:
                schedule_or_send_campaign(
                    campaign, send_now=False, scheduled_at=scheduled_at
                )
                messages.success(
                    request,
                    f"Campaign scheduled for {timezone.localtime(scheduled_at):%b %d, %Y %H:%M}.",
                )
            except ValueError as exc:
                messages.error(request, str(exc))
            return redirect("campaign_detail", pk=pk)

        if action == "cancel" and (
            campaign.can_cancel or campaign.status == Campaign.Status.DRAFT
        ):
            cancel_campaign(campaign)
            messages.success(request, "Campaign cancelled.")
            return redirect("campaign_detail", pk=pk)

        if action == "delete" and campaign.status in {
            Campaign.Status.DRAFT,
            Campaign.Status.CANCELLED,
        }:
            name = campaign.name
            from audit.service import log_campaign_change

            log_campaign_change(
                campaign,
                action="campaign.deleted",
                summary=f"Deleted campaign “{name}”",
                actor=request.user,
            )
            campaign.delete()
            messages.success(request, f"Deleted “{name}”.")
            return redirect("campaign_index")

        messages.error(request, "That action is not available for this campaign.")
        return redirect("campaign_detail", pk=pk)


class CampaignReportView(OrganisorAndLoginRequiredMixin, View):
    def get(self, request, pk):
        campaign = get_object_or_404(
            Campaign.objects.select_related("contact_list", "template"),
            pk=pk,
            organisation=request.organisation,
        )
        metrics = campaign_metrics(campaign)
        return render(
            request,
            "app/campaigns/report.html",
            {
                "topbar_title": f"{campaign.name} · Report",
                "campaign": campaign,
                "metrics": metrics,
            },
        )
