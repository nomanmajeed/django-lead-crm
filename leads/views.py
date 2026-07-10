from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import send_mail
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
    """Organiser home — empty-state onboarding until ticket 12 expands KPIs."""

    template_name = "app/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organisation = self.request.organisation
        lead_count = Lead.objects.for_org(organisation).count() if organisation else 0
        agent_count = (
            Agent.objects.for_org(organisation).count() if organisation else 0
        )
        context.update(
            {
                "topbar_title": "Dashboard",
                "organisation": organisation,
                "lead_count": lead_count,
                "agent_count": agent_count,
                "is_empty": lead_count == 0 and agent_count == 0,
            }
        )
        return context


class AgentHomeView(LoginRequiredMixin, generic.TemplateView):
    """Agent workspace home."""

    template_name = "agent/home.html"
    login_url = "login"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not user_is_agent_member(request.user):
            if user_can_manage_organisation(request.user):
                return redirect("app_home")
            return redirect("landing_page")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organisation = self.request.organisation
        user = self.request.user
        leads = Lead.objects.none()
        if organisation:
            leads = Lead.objects.for_org(organisation).filter(
                agent__isnull=False,
                agent__user=user,
            )
        context.update(
            {
                "topbar_title": "My work",
                "organisation": organisation,
                "leads": leads,
                "lead_count": leads.count(),
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
def lead_detail(request, pk):
    lead = get_object_or_404(_agent_scoped_leads(request), pk=pk)
    return render(
        request,
        _space_template(request, "leads/lead_detail.html", "agent/lead_detail.html"),
        {"lead": lead, "topbar_title": f"{lead.first_name} {lead.last_name}"},
    )

@login_required
@user_is_organisor
def lead_create(request):
    form = LeadModelFrom()
    if request.method == "POST":
        form = LeadModelFrom(request.POST)
        if form.is_valid():
            lead = form.save(commit=False)
            lead.organisation = request.organisation
            lead.save()
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
    form = LeadModelFrom(instance=lead)

    if request.method == "POST":
        form = LeadModelFrom(request.POST, instance=lead)
        if form.is_valid():
            form.save()
            return redirect(reverse("leads:lead_list"))

    return render(request, "leads/lead_update.html", {"form": form, "lead": lead})


@login_required
@user_is_organisor
def lead_delete(request, pk):
    lead = get_object_or_404(Lead.objects.for_org(request.organisation), pk=pk)
    if request.method == "POST":
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
        return reverse("leads:lead_list")

    def form_valid(self, form):
        agent = form.cleaned_data["agent"]
        lead = get_object_or_404(
            Lead.objects.for_org(self.request.organisation),
            pk=self.kwargs["pk"],
        )
        lead.agent = agent
        lead.save()
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["topbar_title"] = "Update category"
        return context