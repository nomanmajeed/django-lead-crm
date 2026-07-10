"""Organiser lead pipeline — board + list views over org-scoped categories."""

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from agents.mixins import OrganisorAndLoginRequiredMixin

from leads.models import Agent, Category, Lead

DEFAULT_PIPELINE_STAGES = (
    "New",
    "Contacted",
    "Qualified",
    "Won",
    "Lost",
)


def ensure_pipeline_stages(organisation):
    """Create default stage categories for an org when missing."""
    if organisation is None:
        return Category.objects.none()

    existing = {
        cat.name.lower(): cat for cat in Category.objects.for_org(organisation)
    }
    for stage_name in DEFAULT_PIPELINE_STAGES:
        if stage_name.lower() not in existing:
            Category.objects.create(name=stage_name, organisation=organisation)
    return Category.objects.for_org(organisation).order_by("id")


def filter_pipeline_leads(organisation, *, q="", agent_id="", stage=""):
    leads = Lead.objects.for_org(organisation).select_related(
        "category", "agent", "agent__user"
    )
    if q:
        leads = leads.filter(
            Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(email__icontains=q)
            | Q(phone_number__icontains=q)
        )
    if agent_id == "unassigned":
        leads = leads.filter(agent__isnull=True)
    elif agent_id:
        leads = leads.filter(agent_id=agent_id)
    if stage == "uncategorized":
        leads = leads.filter(category__isnull=True)
    elif stage:
        leads = leads.filter(category_id=stage)
    return leads.order_by("-date_added")


class PipelineView(OrganisorAndLoginRequiredMixin, View):
    """Board/list pipeline with org-scoped filters and stage moves."""

    def get(self, request):
        organisation = request.organisation
        categories = ensure_pipeline_stages(organisation)
        q = request.GET.get("q", "").strip()
        agent_id = request.GET.get("agent", "").strip()
        stage = request.GET.get("stage", "").strip()
        view_mode = request.GET.get("view", "board")
        if view_mode not in {"board", "list"}:
            view_mode = "board"

        leads = filter_pipeline_leads(
            organisation, q=q, agent_id=agent_id, stage=stage
        )
        columns = [("uncategorized", "Uncategorized", leads.filter(category__isnull=True))]
        for category in categories:
            columns.append(
                (
                    str(category.pk),
                    category.name,
                    leads.filter(category=category),
                )
            )

        return render(
            request,
            "leads/pipeline.html",
            {
                "topbar_title": "Pipeline",
                "organisation": organisation,
                "categories": categories,
                "agents": Agent.objects.for_org(organisation).select_related("user"),
                "leads": leads,
                "columns": columns,
                "view_mode": view_mode,
                "filters": {"q": q, "agent": agent_id, "stage": stage},
                "lead_count": leads.count(),
            },
        )

    def post(self, request):
        organisation = request.organisation
        ensure_pipeline_stages(organisation)
        lead = get_object_or_404(
            Lead.objects.for_org(organisation),
            pk=request.POST.get("lead_id"),
        )
        category_id = request.POST.get("category_id", "").strip()
        if category_id in {"", "uncategorized", "none"}:
            lead.category = None
            stage_label = "Uncategorized"
        else:
            category = get_object_or_404(
                Category.objects.for_org(organisation),
                pk=category_id,
            )
            lead.category = category
            stage_label = category.name
        lead.save(update_fields=["category"])
        from leads.models import LeadActivity, record_lead_activity

        record_lead_activity(
            lead,
            kind=LeadActivity.Kind.STATUS,
            summary=f"Stage set to {stage_label}",
            actor=request.user,
        )
        messages.success(
            request,
            f"Moved {lead.first_name} {lead.last_name} to {stage_label}.",
        )

        params = request.GET.urlencode()
        redirect_url = reverse_pipeline(params)
        return redirect(redirect_url)


def reverse_pipeline(querystring=""):
    from django.urls import reverse

    url = reverse("leads:pipeline")
    if querystring:
        return f"{url}?{querystring}"
    return url
