import random
from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import send_mail
from django.views import generic
from django.shortcuts import reverse
from leads.models import Agent
from .forms import AgentModelForm
from .mixins import OrganisorAndLoginRequiredMixin


# Create your views here.
class AgentListView(OrganisorAndLoginRequiredMixin, generic.ListView):
    template_name = "agents/agent_list.html"

    def get_queryset(self):
        return Agent.objects.filter(organisation=self.request.user.userprofile)


class AgentCreateView(OrganisorAndLoginRequiredMixin, generic.CreateView):
    template_name = "agents/agent_create.html"
    form_class = AgentModelForm

    def get_success_url(self):
        return reverse("agents:agent_list")

    def form_valid(self, form):
        user = form.save(commit=False)
        user.is_agent = True
        user.is_organisor = False
        user.set_password(f"{random.randint(0,1000000)}")
        user.save()

        Agent.objects.create(user=user, organisation=self.request.user.userprofile)
        # agent = form.save(commit=False)
        # agent.organisation = self.request.user.userprofile
        # agent.save()
        send_mail(
            subject="You are invited to be an agent",
            message="You are added as an Agent. Please login ansd start working",
            from_email="admin@test.com",
            recipient_list=[user.email],
        )

        return super(AgentCreateView, self).form_valid(form)


class AgentDetailView(OrganisorAndLoginRequiredMixin, generic.DetailView):
    template_name = "agents/agent_detail.html"
    context_object_name = "agent"

    def get_queryset(self):
        return Agent.objects.filter(organisation=self.request.user.userprofile)


class AgentUpdateView(OrganisorAndLoginRequiredMixin, generic.UpdateView):
    template_name = "agents/agent_update.html"
    form_class = AgentModelForm

    def get_success_url(self):
        return reverse("agents:agent_list")

    def get_queryset(self):
        return Agent.objects.all()


class AgentDeleteView(OrganisorAndLoginRequiredMixin, generic.DeleteView):
    template_name = "agents/agent_delete.html"
    context_object_name = "agent"

    def get_success_url(self):
        return reverse("agents:agent_list")

    def get_queryset(self):
        return Agent.objects.filter(organisation=self.request.user.userprofile)
