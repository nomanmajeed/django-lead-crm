from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, UsernameField
from django.utils.text import slugify

from .models import Agent, Lead, unique_org_slug

User = get_user_model()


class CustomUserCreationForm(UserCreationForm):
    company_name = forms.CharField(
        max_length=120,
        label="Company name",
        help_text="This becomes your organisation workspace.",
    )
    email = forms.EmailField(required=False, label="Work email")

    class Meta:
        model = User
        fields = ("username", "email", "company_name")
        field_classes = {"username": UsernameField}

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            self._apply_organisation_name(user)
        return user

    def _apply_organisation_name(self, user):
        company_name = self.cleaned_data["company_name"].strip()
        organisation = user.owned_organisation
        organisation.name = company_name
        organisation.slug = unique_org_slug(
            slugify(company_name) or f"org-{user.pk}",
            exclude_pk=organisation.pk,
        )
        organisation.save(update_fields=["name", "slug", "updated_at"])


class LeadFrom(forms.Form):
    first_name = forms.CharField()
    last_name = forms.CharField()
    age = forms.IntegerField(min_value=0)


class LeadModelFrom(forms.ModelForm):
    class Meta:
        model = Lead
        fields = (
            "first_name",
            "last_name",
            "age",
            "agent",
            "description",
            "phone_number",
            "email",
        )

    def __init__(self, *args, **kwargs):
        organisation = kwargs.pop("organisation", None)
        super().__init__(*args, **kwargs)
        self.fields["agent"].required = False
        self.fields["agent"].empty_label = "Unassigned (auto-assign if enabled)"
        if organisation is not None:
            self.fields["agent"].queryset = Agent.objects.for_org(organisation)
        elif self.instance and self.instance.pk and self.instance.organisation_id:
            self.fields["agent"].queryset = Agent.objects.for_org(
                self.instance.organisation
            )


class AssignAgentForm(forms.Form):
    agent = forms.ModelChoiceField(queryset=Agent.objects.none())

    def __init__(self, *args, **kwargs):
        request = kwargs.pop("request")
        agents = Agent.objects.for_org(request.organisation)
        super().__init__(*args, **kwargs)
        self.fields["agent"].queryset = agents
        self.fields["agent"].widget.attrs.update(
            {"class": "select select-bordered select-sm w-full"}
        )


class LeadCategoryUpdateForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ("category",)

    def __init__(self, *args, **kwargs):
        organisation = kwargs.pop("organisation", None)
        super().__init__(*args, **kwargs)
        from .models import Category

        if organisation is not None:
            self.fields["category"].queryset = Category.objects.for_org(organisation)
        elif self.instance and self.instance.pk and self.instance.organisation_id:
            self.fields["category"].queryset = Category.objects.for_org(
                self.instance.organisation
            )
