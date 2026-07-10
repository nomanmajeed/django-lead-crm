"""Org-scoped static contact lists and dynamic segments."""

from datetime import timedelta

from django import forms
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from agents.mixins import OrganisorAndLoginRequiredMixin

from leads.models import ContactList, ContactListMembership, Lead
from leads.pipeline import ensure_pipeline_stages

NEW_LEADS_SEGMENT_NAME = "New leads last 7 days"


def resolve_list_members(contact_list: ContactList):
    """Return org-scoped Lead queryset for a static list or segment."""
    organisation = contact_list.organisation
    if contact_list.kind == ContactList.Kind.STATIC:
        return Lead.objects.for_org(organisation).filter(
            list_memberships__contact_list=contact_list
        ).distinct()

    filters = contact_list.filters or {}
    qs = Lead.objects.for_org(organisation)
    days = filters.get("date_added_days")
    if days:
        try:
            days_int = int(days)
            qs = qs.filter(date_added__gte=timezone.now() - timedelta(days=days_int))
        except (TypeError, ValueError):
            pass
    stage = (filters.get("stage") or "").strip()
    if stage:
        if stage.lower() == "uncategorized":
            qs = qs.filter(category__isnull=True)
        elif stage.isdigit():
            qs = qs.filter(category_id=int(stage))
        else:
            qs = qs.filter(category__name__iexact=stage)
    source = (filters.get("source") or "").strip()
    if source:
        qs = qs.filter(custom_fields__source__iexact=source)
    tag = (filters.get("tag") or "").strip()
    if tag:
        # Tags stored as custom_fields.tag (string) or custom_fields.tags (list)
        qs = qs.filter(
            Q(custom_fields__tag__iexact=tag)
            | Q(custom_fields__tags__icontains=tag)
        )
    return qs.order_by("-date_added")


def ensure_default_segments(organisation):
    if organisation is None:
        return
    ContactList.objects.get_or_create(
        organisation=organisation,
        name=NEW_LEADS_SEGMENT_NAME,
        defaults={
            "kind": ContactList.Kind.SEGMENT,
            "filters": {"date_added_days": 7},
        },
    )


class ContactListForm(forms.ModelForm):
    date_added_days = forms.IntegerField(
        required=False, min_value=1, label="Added within last N days"
    )
    stage = forms.CharField(required=False, label="Stage name or id")
    source = forms.CharField(required=False, label="Source (custom field)")
    tag = forms.CharField(required=False, label="Tag")

    class Meta:
        model = ContactList
        fields = ("name", "kind")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        filters = (self.instance.filters if self.instance.pk else {}) or {}
        self.fields["date_added_days"].initial = filters.get("date_added_days")
        self.fields["stage"].initial = filters.get("stage", "")
        self.fields["source"].initial = filters.get("source", "")
        self.fields["tag"].initial = filters.get("tag", "")
        for name in self.fields:
            widget = self.fields[name].widget
            css = "input input-bordered input-sm w-full"
            if name == "kind":
                css = "select select-bordered select-sm w-full"
            widget.attrs.setdefault("class", css)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("kind") == ContactList.Kind.SEGMENT:
            filters = {}
            if cleaned.get("date_added_days"):
                filters["date_added_days"] = cleaned["date_added_days"]
            if cleaned.get("stage"):
                filters["stage"] = cleaned["stage"].strip()
            if cleaned.get("source"):
                filters["source"] = cleaned["source"].strip()
            if cleaned.get("tag"):
                filters["tag"] = cleaned["tag"].strip()
            if not filters:
                raise forms.ValidationError(
                    "Segments need at least one filter (days, stage, source, or tag)."
                )
            cleaned["filters"] = filters
        else:
            cleaned["filters"] = {}
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.filters = self.cleaned_data.get("filters") or {}
        if commit:
            instance.save()
        return instance


class ContactListIndexView(OrganisorAndLoginRequiredMixin, View):
    def get(self, request):
        organisation = request.organisation
        ensure_default_segments(organisation)
        lists = ContactList.objects.for_org(organisation).order_by("kind", "name")
        rows = []
        for item in lists:
            rows.append(
                {
                    "list": item,
                    "member_count": resolve_list_members(item).count(),
                }
            )
        return render(
            request,
            "app/lists/index.html",
            {
                "topbar_title": "Lists",
                "rows": rows,
            },
        )


class ContactListCreateView(OrganisorAndLoginRequiredMixin, View):
    def get(self, request):
        return render(
            request,
            "app/lists/form.html",
            {
                "topbar_title": "New list",
                "form": ContactListForm(),
                "heading": "Create list or segment",
            },
        )

    def post(self, request):
        form = ContactListForm(request.POST)
        if form.is_valid():
            contact_list = form.save(commit=False)
            contact_list.organisation = request.organisation
            contact_list.save()
            messages.success(request, f"Created “{contact_list.name}”.")
            return redirect("list_detail", pk=contact_list.pk)
        return render(
            request,
            "app/lists/form.html",
            {
                "topbar_title": "New list",
                "form": form,
                "heading": "Create list or segment",
            },
        )


class ContactListDetailView(OrganisorAndLoginRequiredMixin, View):
    def get(self, request, pk):
        contact_list = get_object_or_404(
            ContactList.objects.for_org(request.organisation), pk=pk
        )
        members = resolve_list_members(contact_list)[:50]
        available = Lead.objects.none()
        if contact_list.kind == ContactList.Kind.STATIC:
            available = (
                Lead.objects.for_org(request.organisation)
                .exclude(list_memberships__contact_list=contact_list)
                .order_by("-date_added")[:100]
            )
        return render(
            request,
            "app/lists/detail.html",
            {
                "topbar_title": contact_list.name,
                "contact_list": contact_list,
                "members": members,
                "member_count": resolve_list_members(contact_list).count(),
                "available_leads": available,
                "categories": ensure_pipeline_stages(request.organisation),
            },
        )

    def post(self, request, pk):
        contact_list = get_object_or_404(
            ContactList.objects.for_org(request.organisation), pk=pk
        )
        action = request.POST.get("action")
        if contact_list.kind != ContactList.Kind.STATIC:
            messages.error(request, "Only static lists support manual membership.")
            return redirect("list_detail", pk=pk)

        if action == "add":
            lead = get_object_or_404(
                Lead.objects.for_org(request.organisation),
                pk=request.POST.get("lead_id"),
            )
            ContactListMembership.objects.get_or_create(
                contact_list=contact_list, lead=lead
            )
            messages.success(request, f"Added {lead}.")
        elif action == "remove":
            ContactListMembership.objects.filter(
                contact_list=contact_list,
                lead_id=request.POST.get("lead_id"),
            ).delete()
            messages.success(request, "Removed from list.")
        return redirect("list_detail", pk=pk)
