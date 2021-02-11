from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import send_mail
from django.http import HttpResponse
from django.views import generic
from django.shortcuts import render, redirect, reverse
from .models import Lead, Agent
from .forms import LeadFrom, LeadModelFrom, CustomUserCreationForm

# Create your views here.


def landing_page(request):

    return render(request, "landing_page.html")


@login_required
def lead_list(request):

    leads = Lead.objects.all()
    context = {"leads": leads}

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
def lead_delete(request, pk):

    if request.method == "POST":
        lead = Lead.objects.get(id=pk)
        lead.delete()

        return redirect("/leads/")

    return render(request, "leads/lead_delete.html")
