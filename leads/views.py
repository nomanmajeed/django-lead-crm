from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import send_mail
from django.http import HttpResponse
from django.views import generic
from django.shortcuts import render, redirect, reverse
from .models import Lead, Agent, Category
from .forms import (
    LeadFrom,
    LeadModelFrom,
    CustomUserCreationForm,
    AssignAgentForm,
    LeadCategoryUpdateForm,
)
from .decorators import user_is_organisor
from agents.mixins import OrganisorAndLoginRequiredMixin

# Create your views here.


def landing_page(request):

    return render(request, "landing_page.html")


@login_required
def lead_list(request):
    user = request.user
    leads = None

    if user.is_organisor:
        leads = Lead.objects.filter(organisation=user.userprofile, agent__isnull=False)
    if user.is_agent:
        leads = Lead.objects.filter(
            organisation=user.agent.organisation, agent__isnull=False
        )
        leads = leads.filter(agent__user=user)

    context = {"leads": leads}

    if user.is_organisor:
        queryset = Lead.objects.filter(
            organisation=user.userprofile, agent__isnull=True
        )
        context["unassigned_leads"] = queryset

    return render(request, "leads/lead_list.html", context)


@login_required
def lead_detail(request, pk):

    lead = Lead.objects.get(id=pk)
    context = {"lead": lead}

    return render(request, "leads/lead_detail.html", context)


# def lead_create(request):
#     print("Create Lead View")
#     print(request.POST)
#     form = LeadFrom()
#     if request.method == "POST":
#         print("POST: Recieving Form Values")
#         form = LeadFrom(request.POST)

#         if form.is_valid():
#             print("Form is valid")
#             print(form.cleaned_data)

#             first_name = form.cleaned_data["first_name"]
#             last_name = form.cleaned_data["last_name"]
#             age = form.cleaned_data["age"]
#             agent = Agent.objects.first()

#             Lead.objects.create(
#                 first_name=first_name, last_name=last_name, age=age, agent=agent
#             )
#             print("New Lead Created")

#             return redirect("/leads")

#     context = {"form": form}

#     return render(request, "leads/lead_create.html", context)


# def lead_update(request, pk):
#     print("Update Lead View")
#     print("ID: ", pk)

#     lead = Lead.objects.get(id=pk)

#     print("LEAD: ", lead)
#     print(request.POST)
#     form = LeadFrom()

#     if request.method == "POST":
#         print("POST: Recieving Form Values for Update")
#         print(request.POST)
#         form = LeadFrom(request.POST)

#         if form.is_valid():
#             print("Form is valid")
#             print(form.cleaned_data)

#             first_name = form.cleaned_data["first_name"]
#             last_name = form.cleaned_data["last_name"]
#             age = form.cleaned_data["age"]

#             lead.first_name = first_name
#             lead.last_name = last_name
#             lead.age = age
#             lead.save()
#             print("Lead Updated")

#             return redirect("/leads")

#     context = {"form": form, "lead": lead}

#     return render(request, "leads/lead_update.html", context)


# class SignupView(LoginRequiredMixin, generic.CreateView):
#     template_name = "registration/signup.html"
#     form_class = CustomUserCreationForm

#     def get_success_url(self):
#         return reverse("login")


class SignupView(generic.CreateView):
    template_name = "registration/signup.html"
    form_class = CustomUserCreationForm

    def get_success_url(self):
        return reverse("login")


@login_required
@user_is_organisor
def lead_create(request):
    print("Create Lead View")
    print(request.POST)
    form = LeadModelFrom()
    if request.method == "POST":
        print("POST: Recieving Form Values")
        form = LeadModelFrom(request.POST)

        if form.is_valid():
            print("Form is valid")
            print(form.cleaned_data)

            form.save()

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
    print("Update Lead View")
    print("ID: ", pk)

    lead = Lead.objects.get(id=pk)

    print("LEAD: ", lead)
    print(request.POST)
    form = LeadModelFrom(instance=lead)

    if request.method == "POST":
        print("POST: Recieving Form Values for Update")
        print(request.POST)
        form = LeadModelFrom(request.POST, instance=lead)

        if form.is_valid():
            print("Form is valid")
            print(form.cleaned_data)

            form.save()
            print("Lead Updated")

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
        kwargs = super(AssignAgentView, self).get_form_kwargs(**kwargs)
        kwargs.update({"request": self.request})
        return kwargs

    def get_success_url(self):
        return reverse("leads:lead-list")

    def form_valid(self, form):
        agent = form.cleaned_data["agent"]
        lead = Lead.objects.get(id=self.kwargs["pk"])
        lead.agent = agent
        lead.save()
        return super(AssignAgentView, self).form_valid(form)


class CategoryListView(LoginRequiredMixin, generic.ListView):
    template_name = "leads/category_list.html"
    context_object_name = "category_list"

    def get_context_data(self, **kwargs):
        context = super(CategoryListView, self).get_context_data(**kwargs)
        user = self.request.user

        if user.is_organisor:
            queryset = Lead.objects.filter(organisation=user.userprofile)
        else:
            queryset = Lead.objects.filter(organisation=user.agent.organisation)

        context.update(
            {"unassigned_lead_count": queryset.filter(category__isnull=True).count()}
        )

        return context

    def get_queryset(self):
        user = self.request.user

        if user.is_organisor:
            queryset = Category.objects.filter(organisation=user.userprofile)
        else:
            queryset = Category.objects.filter(organisation=user.agent.organisation)

        return queryset


class CategoryDetailView(LoginRequiredMixin, generic.DetailView):
    template_name = "leads/category_detail.html"
    context_object_name = "category"

    def get_context_data(self, **kwargs):
        context = super(CategoryDetailView, self).get_context_data(**kwargs)

        leads = self.get_object().lead_set.all()

        context.update({"leads": leads})

        return context

    def get_queryset(self):
        user = self.request.user

        if user.is_organisor:
            queryset = Category.objects.filter(organisation=user.userprofile)
        else:
            queryset = Category.objects.filter(organisation=user.agent.organisation)

        return queryset


class LeadCategoryUpdateView(LoginRequiredMixin, generic.UpdateView):
    template_name = "leads/category_update.html"
    form_class = LeadCategoryUpdateForm

    def get_success_url(self):
        return reverse("leads:lead_detail", kwargs={"pk": self.get_object().id})

    def get_queryset(self):
        user = self.request.user

        if user.is_organisor:
            queryset = Lead.objects.filter(organisation=user.userprofile)
        else:
            queryset = Lead.objects.filter(organisation=user.agent.organisation)

        return queryset
