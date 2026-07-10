from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import send_mail
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render, reverse
from django.views import generic

from agents.mixins import OrganisorAndLoginRequiredMixin

from .decorators import user_is_organisor
from .forms import (
    AssignAgentForm,
    CustomUserCreationForm,
    LeadCategoryUpdateForm,
    LeadModelFrom,
)
from .models import Agent, Category, Lead
from .permissions import user_can_manage_organisation, user_is_agent_member


def landing_page(request):
    return render(request, "landing_page.html")


class SignupView(generic.CreateView):
    template_name = "registration/signup.html"
    form_class = CustomUserCreationForm

    def form_valid(self, form):
        self.object = form.save()
        login(self.request, self.object)
        return redirect("app_home")


class AppHomeView(OrganisorAndLoginRequiredMixin, generic.TemplateView):
    """Organiser home with KPIs, activity, and quick actions."""

    template_name = "app/home.html"

    def get_context_data(self, **kwargs):
        from datetime import timedelta

        from django.utils import timezone

        from leads.models import Invite

        context = super().get_context_data(**kwargs)
        organisation = self.request.organisation
        leads = Lead.objects.for_org(organisation) if organisation else Lead.objects.none()
        agents = (
            Agent.objects.for_org(organisation) if organisation else Agent.objects.none()
        )

        week_ago = timezone.now() - timedelta(days=7)
        lead_count = leads.count()
        new_leads = leads.filter(date_added__gte=week_ago).count()
        unassigned = leads.filter(agent__isnull=True).count()
        converted = leads.filter(category__name__iexact="converted").count()
        open_pipeline = lead_count - converted
        conversion_rate = (
            round((converted / lead_count) * 100) if lead_count else 0
        )
        recent_leads = leads.order_by("-date_added")[:5]
        recent_invites = (
            Invite.objects.filter(organisation=organisation).order_by("-created_at")[:5]
            if organisation
            else Invite.objects.none()
        )

        from email_engine.analytics import (
            org_weekly_email_summary,
            recent_campaign_reports,
        )

        email_week = org_weekly_email_summary(organisation, days=7)
        campaign_reports = recent_campaign_reports(organisation, limit=5)

        from leads.onboarding import onboarding_snapshot

        context.update(
            {
                "topbar_title": "Dashboard",
                "organisation": organisation,
                "lead_count": lead_count,
                "agent_count": agents.count(),
                "new_leads": new_leads,
                "open_pipeline": open_pipeline,
                "conversion_rate": conversion_rate,
                "campaign_sends": email_week["sent"],
                "email_week": email_week,
                "campaign_reports": campaign_reports,
                "unassigned_count": unassigned,
                "is_empty": lead_count == 0 and agents.count() == 0,
                "recent_leads": recent_leads,
                "recent_invites": recent_invites,
                "onboarding": onboarding_snapshot(organisation),
            }
        )
        return context


class AgentHomeView(LoginRequiredMixin, generic.TemplateView):
    """Agent workspace home — assigned leads, follow-ups, quick stage updates."""

    template_name = "agent/home.html"
    login_url = "login"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not user_is_agent_member(request.user):
            if user_can_manage_organisation(request.user):
                return redirect("app_home")
            return redirect("landing_page")
        return super().dispatch(request, *args, **kwargs)

    def _assigned_leads(self):
        organisation = self.request.organisation
        if not organisation:
            return Lead.objects.none()
        return (
            Lead.objects.for_org(organisation)
            .filter(agent__isnull=False, agent__user=self.request.user)
            .select_related("category", "agent")
            .order_by("-date_added")
        )

    def post(self, request, *args, **kwargs):
        from django.contrib import messages

        lead_id = request.POST.get("lead_id")
        category_id = request.POST.get("category_id") or None
        lead = get_object_or_404(self._assigned_leads(), pk=lead_id)
        if category_id:
            category = get_object_or_404(
                Category.objects.for_org(request.organisation),
                pk=category_id,
            )
            lead.category = category
        else:
            lead.category = None
        lead.save(update_fields=["category"])
        messages.success(
            request,
            f"Updated {lead.first_name} {lead.last_name} to "
            f"{lead.category.name if lead.category else 'Unassigned'}.",
        )
        return redirect("agent_home")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organisation = self.request.organisation
        leads = self._assigned_leads()
        follow_ups = leads.filter(
            Q(category__isnull=True)
            | Q(category__name__iexact="new")
            | Q(category__name__iexact="contacted")
        )
        categories = (
            Category.objects.for_org(organisation)
            if organisation
            else Category.objects.none()
        )
        context.update(
            {
                "topbar_title": "My work",
                "organisation": organisation,
                "leads": leads[:10],
                "lead_count": leads.count(),
                "follow_ups": follow_ups[:8],
                "follow_up_count": follow_ups.count(),
                "categories": categories,
                "is_empty": not leads.exists(),
                "recent_leads": leads[:5],
            }
        )
        return context


def _agent_scoped_leads(request):
    qs = Lead.objects.for_org(request.organisation)
    user = request.user
    if user_is_agent_member(user) and not user_can_manage_organisation(user):
        qs = qs.filter(agent__isnull=False, agent__user=user)
    return qs


def _space_template(request, organiser_name, agent_name):
    if getattr(request, "product_space", None) == "agent":
        return agent_name
    return organiser_name


@login_required
def lead_list(request):
    user = request.user
    organisation = request.organisation
    context = {"leads": Lead.objects.none(), "topbar_title": "Leads"}

    if organisation and user_can_manage_organisation(user, organisation):
        context["leads"] = Lead.objects.for_org(organisation).filter(
            agent__isnull=False
        )
        context["unassigned_leads"] = Lead.objects.for_org(organisation).filter(
            agent__isnull=True
        )
    elif organisation and user_is_agent_member(user, organisation):
        context["leads"] = Lead.objects.for_org(organisation).filter(
            agent__isnull=False,
            agent__user=user,
        )
        context["topbar_title"] = "My leads"

    return render(
        request,
        _space_template(request, "leads/lead_list.html", "agent/lead_list.html"),
        context,
    )


@login_required
@user_is_organisor
def lead_create(request):
    form = LeadModelFrom(organisation=request.organisation)
    if request.method == "POST":
        form = LeadModelFrom(request.POST, organisation=request.organisation)
        if form.is_valid():
            from leads.assignment import maybe_auto_assign

            lead = form.save(commit=False)
            lead.organisation = request.organisation
            lead.save()
            maybe_auto_assign(lead, actor=request.user)
            from audit.service import log_lead_change

            log_lead_change(
                lead,
                action="lead.created",
                summary=f"Created lead {lead.first_name} {lead.last_name}",
                actor=request.user,
            )
            send_mail(
                subject="Lead Created",
                message="Visit homepage to see new lead",
                from_email="test@test.com",
                recipient_list=["test2@test.com"],
            )
            return redirect(reverse("leads:lead_list"))

    return render(request, "leads/lead_create.html", {"form": form})


@login_required
@user_is_organisor
def lead_update(request, pk):
    lead = get_object_or_404(Lead.objects.for_org(request.organisation), pk=pk)
    form = LeadModelFrom(instance=lead, organisation=request.organisation)

    if request.method == "POST":
        form = LeadModelFrom(
            request.POST, instance=lead, organisation=request.organisation
        )
        if form.is_valid():
            form.save()
            from audit.service import log_lead_change

            log_lead_change(
                lead,
                action="lead.updated",
                summary=f"Updated lead {lead.first_name} {lead.last_name}",
                actor=request.user,
            )
            return redirect(reverse("leads:lead_list"))

    return render(request, "leads/lead_update.html", {"form": form, "lead": lead})


@login_required
@user_is_organisor
def lead_delete(request, pk):
    lead = get_object_or_404(Lead.objects.for_org(request.organisation), pk=pk)
    if request.method == "POST":
        from audit.service import log_lead_change

        log_lead_change(
            lead,
            action="lead.deleted",
            summary=f"Deleted lead {lead.first_name} {lead.last_name}",
            actor=request.user,
        )
        lead.delete()
        return redirect(reverse("leads:lead_list"))
    return render(request, "leads/lead_delete.html", {"lead": lead})


class AssignAgentView(OrganisorAndLoginRequiredMixin, generic.FormView):
    template_name = "leads/assign_agent.html"
    form_class = AssignAgentForm

    def get_form_kwargs(self, **kwargs):
        kwargs = super().get_form_kwargs(**kwargs)
        kwargs.update({"request": self.request})
        return kwargs

    def get_success_url(self):
        return reverse("leads:pipeline")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["topbar_title"] = "Assign agent"
        return context

    def form_valid(self, form):
        from leads.assignment import assign_lead_to_agent

        agent = form.cleaned_data["agent"]
        lead = get_object_or_404(
            Lead.objects.for_org(self.request.organisation),
            pk=self.kwargs["pk"],
        )
        assign_lead_to_agent(lead, agent, actor=self.request.user)
        return super().form_valid(form)


class CategoryListView(LoginRequiredMixin, generic.ListView):
    template_name = "leads/category_list.html"
    context_object_name = "category_list"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = Lead.objects.for_org(self.request.organisation)
        context.update(
            {"unassigned_lead_count": queryset.filter(category__isnull=True).count()}
        )
        return context

    def get_queryset(self):
        return Category.objects.for_org(self.request.organisation)


class CategoryDetailView(LoginRequiredMixin, generic.DetailView):
    template_name = "leads/category_detail.html"
    context_object_name = "category"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"leads": self.get_object().lead_set.all()})
        return context

    def get_queryset(self):
        return Category.objects.for_org(self.request.organisation)


class LeadCategoryUpdateView(LoginRequiredMixin, generic.UpdateView):
    form_class = LeadCategoryUpdateForm

    def get_template_names(self):
        return [
            _space_template(
                self.request,
                "leads/category_update.html",
                "agent/category_update.html",
            )
        ]

    def get_success_url(self):
        pk = self.get_object().id
        if getattr(self.request, "product_space", None) == "agent":
            return reverse("agent_leads:lead_detail", kwargs={"pk": pk})
        return reverse("leads:lead_detail", kwargs={"pk": pk})

    def get_queryset(self):
        return _agent_scoped_leads(self.request)

    def form_valid(self, form):
        from leads.models import LeadActivity, record_lead_activity

        old = self.get_object().category
        response = super().form_valid(form)
        new = self.object.category
        old_name = old.name if old else "Uncategorized"
        new_name = new.name if new else "Uncategorized"
        if old_name != new_name:
            record_lead_activity(
                self.object,
                kind=LeadActivity.Kind.STATUS,
                summary=f"Stage changed from {old_name} to {new_name}",
                actor=self.request.user,
            )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["topbar_title"] = "Update category"
        return context