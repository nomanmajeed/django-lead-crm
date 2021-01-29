from django import forms
from .models import Lead


class LeadFrom(forms.Form):

    first_name = forms.CharField()
    last_name = forms.CharField()
    age = forms.IntegerField(min_value=0)


class LeadModelFrom(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ("first_name", "last_name", "age", "agent")

