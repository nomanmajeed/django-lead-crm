"""Organiser UI for drip email sequences."""

from django import forms
from django.contrib import messages
from django.forms import inlineformset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from agents.mixins import OrganisorAndLoginRequiredMixin
from billing.entitlements import EntitlementDenied, require_feature, require_within_limit
from billing.gates import feature_or_upgrade
from email_engine.models import (
    EmailSequence,
    EmailTemplate,
    SequenceEnrollment,
    SequenceStep,
)
from email_engine.sequences import (
    activate_sequence,
    advance_due_enrollments,
    cancel_enrollment,
    enroll_lead,
    enroll_list,
    mark_enrollment_replied,
)
from leads.models import ContactList, Lead


class SequenceForm(forms.ModelForm):
    class Meta:
        model = EmailSequence
        fields = (
            "name",
            "exit_on_reply",
            "exit_on_stage_change",
            "exit_on_unsubscribe",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs.setdefault(
            "class", "input input-bordered input-sm w-full"
        )
        for name in (
            "exit_on_reply",
            "exit_on_stage_change",
            "exit_on_unsubscribe",
        ):
            self.fields[name].widget.attrs.setdefault("class", "checkbox")


def make_step_form(organisation):
    class SequenceStepForm(forms.ModelForm):
        class Meta:
            model = SequenceStep
            fields = ("position", "delay_days", "delay_hours", "template")

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            for name, field in self.fields.items():
                if name == "template":
                    field.widget.attrs.setdefault(
                        "class", "select select-bordered select-sm w-full"
                    )
                else:
                    field.widget.attrs.setdefault(
                        "class", "input input-bordered input-sm w-full"
                    )
            self.fields["template"].queryset = EmailTemplate.objects.filter(
                organisation=organisation
            ).order_by("name")

    return SequenceStepForm


def make_step_formset(organisation, *, extra=1):
    return inlineformset_factory(
        EmailSequence,
        SequenceStep,
        form=make_step_form(organisation),
        fields=("position", "delay_days", "delay_hours", "template"),
        extra=extra,
        can_delete=True,
        min_num=1,
        validate_min=True,
    )


class SequenceIndexView(OrganisorAndLoginRequiredMixin, View):
    def get(self, request):
        blocked = feature_or_upgrade(request, "sequences")
        if blocked:
            return blocked
        sequences = EmailSequence.objects.filter(
            organisation=request.organisation
        ).order_by("-created_at")
        return render(
            request,
            "app/sequences/index.html",
            {"topbar_title": "Sequences", "sequences": sequences},
        )


class SequenceCreateView(OrganisorAndLoginRequiredMixin, View):
    def get(self, request):
        blocked = feature_or_upgrade(request, "sequences")
        if blocked:
            return blocked
        FormSet = make_step_formset(request.organisation, extra=3)
        formset = FormSet(
            initial=[
                {"position": 1, "delay_days": 0, "delay_hours": 0},
                {"position": 2, "delay_days": 2, "delay_hours": 0},
                {"position": 3, "delay_days": 5, "delay_hours": 0},
            ]
        )
        return render(
            request,
            "app/sequences/form.html",
            {
                "topbar_title": "New sequence",
                "form": SequenceForm(),
                "formset": formset,
                "heading": "Create sequence",
            },
        )

    def post(self, request):
        blocked = feature_or_upgrade(request, "sequences")
        if blocked:
            return blocked
        form = SequenceForm(request.POST)
        FormSet = make_step_formset(request.organisation, extra=3)
        if form.is_valid():
            try:
                require_feature(request.organisation, "sequences")
                current = EmailSequence.objects.filter(
                    organisation=request.organisation
                ).count()
                require_within_limit(request.organisation, "sequences", current)
            except EntitlementDenied as exc:
                messages.error(request, exc.message)
                return redirect("billing_plans")
            sequence = form.save(commit=False)
            sequence.organisation = request.organisation
            sequence.created_by = request.user
            sequence.status = EmailSequence.Status.DRAFT
            sequence.save()
            formset = FormSet(request.POST, instance=sequence)
            if formset.is_valid():
                formset.save()
                messages.success(
                    request, f"Draft sequence “{sequence.name}” created."
                )
                return redirect("sequence_detail", pk=sequence.pk)
            sequence.delete()
        else:
            formset = FormSet(request.POST)
        return render(
            request,
            "app/sequences/form.html",
            {
                "topbar_title": "New sequence",
                "form": form,
                "formset": formset,
                "heading": "Create sequence",
            },
        )


class SequenceDetailView(OrganisorAndLoginRequiredMixin, View):
    def _get(self, request, pk):
        return get_object_or_404(
            EmailSequence, pk=pk, organisation=request.organisation
        )

    def _context(self, request, sequence, form=None, formset=None):
        ctx = {
            "topbar_title": sequence.name,
            "sequence": sequence,
            "steps": sequence.steps.select_related("template").order_by("position"),
            "enrollments": sequence.enrollments.select_related("lead").order_by(
                "-enrolled_at"
            )[:50],
            "lists": ContactList.objects.for_org(request.organisation).order_by(
                "name"
            ),
            "leads": Lead.objects.for_org(request.organisation)
            .exclude(email="")
            .order_by("first_name", "last_name")[:200],
            "form": form,
            "formset": formset,
            "active_count": sequence.enrollments.filter(
                status=SequenceEnrollment.Status.ACTIVE
            ).count(),
        }
        if sequence.can_edit and form is None:
            ctx["form"] = SequenceForm(instance=sequence)
            ctx["formset"] = make_step_formset(request.organisation, extra=1)(
                instance=sequence
            )
        return ctx

    def get(self, request, pk):
        blocked = feature_or_upgrade(request, "sequences")
        if blocked:
            return blocked
        sequence = self._get(request, pk)
        return render(
            request, "app/sequences/detail.html", self._context(request, sequence)
        )

    def post(self, request, pk):
        blocked = feature_or_upgrade(request, "sequences")
        if blocked:
            return blocked
        sequence = self._get(request, pk)
        action = request.POST.get("action", "save")

        if action == "save" and sequence.can_edit:
            form = SequenceForm(request.POST, instance=sequence)
            FormSet = make_step_formset(request.organisation, extra=1)
            formset = FormSet(request.POST, instance=sequence)
            if form.is_valid() and formset.is_valid():
                form.save()
                formset.save()
                messages.success(request, "Sequence updated.")
                return redirect("sequence_detail", pk=pk)
            messages.error(request, "Fix the errors below.")
            return render(
                request,
                "app/sequences/detail.html",
                self._context(request, sequence, form=form, formset=formset),
            )

        if action == "activate" and sequence.can_edit:
            try:
                activate_sequence(sequence)
                messages.success(request, "Sequence is now active.")
            except (ValueError, EntitlementDenied) as exc:
                messages.error(request, str(exc))
            return redirect("sequence_detail", pk=pk)

        if action == "archive" and sequence.status == EmailSequence.Status.ACTIVE:
            sequence.status = EmailSequence.Status.ARCHIVED
            sequence.save(update_fields=["status", "updated_at"])
            messages.success(request, "Sequence archived.")
            return redirect("sequence_detail", pk=pk)

        if action == "enroll_lead" and sequence.status == EmailSequence.Status.ACTIVE:
            lead = get_object_or_404(
                Lead.objects.for_org(request.organisation),
                pk=request.POST.get("lead_id"),
            )
            try:
                enroll_lead(sequence, lead, actor=request.user)
                messages.success(
                    request, f"Enrolled {lead.first_name} {lead.last_name}."
                )
            except ValueError as exc:
                messages.error(request, str(exc))
            return redirect("sequence_detail", pk=pk)

        if action == "enroll_list" and sequence.status == EmailSequence.Status.ACTIVE:
            contact_list = get_object_or_404(
                ContactList.objects.for_org(request.organisation),
                pk=request.POST.get("list_id"),
            )
            count = enroll_list(sequence, contact_list, actor=request.user)
            messages.success(request, f"Enrolled {count} lead(s) from the list.")
            return redirect("sequence_detail", pk=pk)

        if action == "process_due":
            results = advance_due_enrollments()
            messages.success(
                request,
                (
                    f"Processed {results['processed']} due enrollment(s): "
                    f"{results['sent']} sent, {results['completed']} completed, "
                    f"{results['exited']} exited."
                ),
            )
            return redirect("sequence_detail", pk=pk)

        if action == "cancel_enrollment":
            enrollment = get_object_or_404(
                SequenceEnrollment,
                pk=request.POST.get("enrollment_id"),
                sequence=sequence,
            )
            cancel_enrollment(enrollment)
            messages.success(request, "Enrollment cancelled.")
            return redirect("sequence_detail", pk=pk)

        if action == "mark_replied":
            enrollment = get_object_or_404(
                SequenceEnrollment,
                pk=request.POST.get("enrollment_id"),
                sequence=sequence,
            )
            mark_enrollment_replied(enrollment)
            messages.success(request, "Marked as replied (exit rule applied).")
            return redirect("sequence_detail", pk=pk)

        if action == "delete" and sequence.status in {
            EmailSequence.Status.DRAFT,
            EmailSequence.Status.ARCHIVED,
        }:
            name = sequence.name
            sequence.delete()
            messages.success(request, f"Deleted “{name}”.")
            return redirect("sequence_index")

        messages.error(request, "That action is not available.")
        return redirect("sequence_detail", pk=pk)
