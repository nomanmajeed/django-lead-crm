from django import forms

from capture.models import LeadCaptureForm, default_fields_config
from email_engine.models import EmailSequence


class CaptureFormBuilder(forms.ModelForm):
    show_description = forms.BooleanField(
        required=False,
        label="Include description field",
        initial=True,
    )
    show_age = forms.BooleanField(required=False, label="Include age field")

    class Meta:
        model = LeadCaptureForm
        fields = ("name", "is_active", "auto_sequence")

    def __init__(self, *args, organisation=None, **kwargs):
        self.organisation = organisation
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs.update(
            {"class": "input input-bordered w-full"}
        )
        self.fields["is_active"].widget.attrs.update({"class": "checkbox"})
        self.fields["auto_sequence"].required = False
        self.fields["auto_sequence"].empty_label = "None (no auto-enroll)"
        if organisation is not None:
            self.fields["auto_sequence"].queryset = EmailSequence.objects.filter(
                organisation=organisation,
                status=EmailSequence.Status.ACTIVE,
            )
        if self.instance and self.instance.pk:
            cfg = self.instance.fields_config or default_fields_config()
            self.fields["show_description"].initial = cfg.get("description", {}).get(
                "enabled", True
            )
            self.fields["show_age"].initial = cfg.get("age", {}).get("enabled", False)

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.organisation:
            instance.organisation = self.organisation
        cfg = default_fields_config()
        cfg["description"]["enabled"] = self.cleaned_data.get("show_description", True)
        cfg["age"]["enabled"] = self.cleaned_data.get("show_age", False)
        instance.fields_config = cfg
        if commit:
            instance.save()
        return instance
