from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, UsernameField
from .models import Lead

User = get_user_model()


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username",)
        field_classes = {"usern)ame": UsernameField}


class LeadFrom(forms.Form):

    first_name = forms.CharField()
    last_name = forms.CharField()
    age = forms.IntegerField(min_value=0)


class LeadModelFrom(forms.ModelForm):
    class Meta:
        modal = Lead
        fields = {
            "first_name",
            "last_name",
            "age",
            "agent",
        }

