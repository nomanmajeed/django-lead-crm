from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import send_mail
from django.views import generic
from django.shortcuts import render, redirect, reverse

from agents.mixins import OrganisorAndLoginRequiredMixin

from .decorators import user_is_organisor
from .forms import (
    LeadModelFrom,
    CustomUserCreationForm,
    AssignAgentForm,
    LeadCategoryUpdateForm,
)
from .models import Lead, Category
from .permissions import (
    get_user_organisation,
    user_can_manage_organisation,
    user_is_agent_member,
)


def landing_page(request):
    return render(request, "landing_page.html")


@login_required
def lead_list(request):
    user = request.user
    organisation = get_user_organisation(user)
    leads = Lead.objects.none()
    context = {"leads": leads}

    if organisation and user_can_manage_organisation(user, organisation):
        leads = Lead.objects.filter(
            organisation=organisation, agent__isnull=False
        )
        context["leads"] = leads
        context["unassigned_leads"] = Lead.objects.filter(
            organisation=organisation, agent__isnull=True
        )
    elif organisation and user_is_agent_member(user, organisation):
        context["leads"] = Lead.objects.filter(
            organisation=organisation,
            agent__isnull=False,
            agent__user=user,
        )

    return render(request, "leads/lead_list.html", context)


@login_required
def lead_detail(request, pk):
    lead = Lead.objects.get(id=pk)
    context = {"lead": lead}
    return render(request, "leads/lead_detail.html", context)


class SignupView(generic.CreateView):
    template_name = "registration/signup.html"
    form_class = CustomUserCreationForm

    def get_success_url(self):
        return reverse("login")


@login_required
@user_is_organisor
def lead_create(request):
    form = LeadModelFrom()
    if request.method == "POST":
        form = LeadModelFrom(request.POST)
        if form.is_valid():
            lead = form.save(commit=False)
            lead.organisation = get_user_organisation(request.user)
            lead.save()
            send_mail(
                subject="Lead Created",
                message="Visit homepage to see new lead",
                from_email="test@test.com",
                recipient_list=["test2@test.com"],
            )
            return redirect("/leads")

    context = {"form": form}
    return render(request, "leads/lead_create.html", context)


@login_required
@user_is_organisor
def lead_update(request, pk):
    lead = Lead.objects.get(id=pk)
    form = LeadModelFrom(instance=lead)

    if request.method == "POST":
        form = LeadModelFrom(request.POST, instance=lead)
        if form.is_valid():
            form.save()
            return redirect("/leads")

    context = {"form": form, "lead": lead}
    return render(request, "leads/lead_update.html", context)


@login_required
@user_is_organisor
def lead_delete(request, pk):
    if request.method == "POST":
        lead = Lead.objects.get(id=pk)
        lead.delete()
        return redirect("/leads/")
    return render(request, "leads/lead_delete.html")


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
        lead = Lead.objects.get(id=self.kwargs["pk"])
        lead.agent = agent
        lead.save()
        return super().form_valid(form)


class CategoryListView(LoginRequiredMixin, generic.ListView):
    template_name = "leads/category_list.html"
    context_object_name = "category_list"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organisation = get_user_organisation(self.request.user)
        queryset = Lead.objects.filter(organisation=organisation)
        context.update(
            {"unassigned_lead_count": queryset.filter(category__isnull=True).count()}
        )
        return context

    def get_queryset(self):
        organisation = get_user_organisation(self.request.user)
        return Category.objects.filter(organisation=organisation)


class CategoryDetailView(LoginRequiredMixin, generic.DetailView):
    template_name = "leads/category_detail.html"
    context_object_name = "category"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"leads": self.get_object().lead_set.all()})
        return context

    def get_queryset(self):
        organisation = get_user_organisation(self.request.user)
        return Category.objects.filter(organisation=organisation)


class LeadCategoryUpdateView(LoginRequiredMixin, generic.UpdateView):
    template_name = "leads/category_update.html"
    form_class = LeadCategoryUpdateForm

    def get_success_url(self):
        return reverse("leads:lead_detail", kwargs={"pk": self.get_object().id})

    def get_queryset(self):
        organisation = get_user_organisation(self.request.user)
        return Lead.objects.filter(organisation=organisation)
