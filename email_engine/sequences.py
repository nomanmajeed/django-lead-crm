"""Drip sequence enrollment, exit rules, and step advancement."""

from __future__ import annotations

from django.utils import timezone

from email_engine.merge import build_merge_context, render_merge
from email_engine.models import (
    EmailSequence,
    EmailSuppression,
    OutboundEmail,
    SequenceEnrollment,
    SequenceStep,
    SequenceStepSend,
)
from email_engine.service import queue_transactional_email
from leads.lists import resolve_list_members
from leads.models import LeadActivity, record_lead_activity


def is_email_suppressed(organisation, email: str) -> bool:
    email = (email or "").strip().lower()
    if not email or organisation is None:
        return False
    return EmailSuppression.objects.filter(
        organisation=organisation, email__iexact=email
    ).exists()


def suppress_email(organisation, email: str, *, reason: str = "unsubscribe"):
    email = (email or "").strip().lower()
    if not email:
        return None
    obj, _ = EmailSuppression.objects.get_or_create(
        organisation=organisation,
        email=email,
        defaults={"reason": reason},
    )
    return obj


def _exit_enrollment(
    enrollment: SequenceEnrollment, reason: str
) -> SequenceEnrollment:
    enrollment.status = SequenceEnrollment.Status.EXITED
    enrollment.exit_reason = reason
    enrollment.completed_at = timezone.now()
    enrollment.next_run_at = None
    enrollment.save(
        update_fields=["status", "exit_reason", "completed_at", "next_run_at"]
    )
    record_lead_activity(
        enrollment.lead,
        kind=LeadActivity.Kind.CUSTOM,
        summary=(
            f"Exited sequence “{enrollment.sequence.name}” "
            f"({enrollment.get_exit_reason_display()})"
        ),
    )
    return enrollment


def check_exit_rules(enrollment: SequenceEnrollment) -> str | None:
    """Return exit reason if enrollment should stop, else None."""
    if enrollment.status != SequenceEnrollment.Status.ACTIVE:
        return enrollment.exit_reason or None

    sequence = enrollment.sequence
    lead = enrollment.lead

    if sequence.exit_on_reply and enrollment.reply_detected_at:
        return SequenceEnrollment.ExitReason.REPLY

    if sequence.exit_on_stage_change:
        if enrollment.enrolled_category_id != lead.category_id:
            return SequenceEnrollment.ExitReason.STAGE_CHANGE

    if sequence.exit_on_unsubscribe:
        if is_email_suppressed(sequence.organisation, lead.email):
            return SequenceEnrollment.ExitReason.UNSUBSCRIBE
        if (lead.custom_fields or {}).get("unsubscribed"):
            return SequenceEnrollment.ExitReason.UNSUBSCRIBE

    return None


def mark_enrollment_replied(
    enrollment: SequenceEnrollment,
) -> SequenceEnrollment:
    enrollment.reply_detected_at = timezone.now()
    enrollment.save(update_fields=["reply_detected_at"])
    if (
        enrollment.sequence.exit_on_reply
        and enrollment.status == SequenceEnrollment.Status.ACTIVE
    ):
        return _exit_enrollment(enrollment, SequenceEnrollment.ExitReason.REPLY)
    return enrollment


def enroll_lead(sequence: EmailSequence, lead, *, actor=None) -> SequenceEnrollment:
    if sequence.status != EmailSequence.Status.ACTIVE:
        raise ValueError("Only active sequences accept enrollments.")
    if not sequence.steps.exists():
        raise ValueError("Sequence has no steps.")
    email = (lead.email or "").strip()
    if not email:
        raise ValueError("Lead has no email address.")
    if is_email_suppressed(sequence.organisation, email):
        raise ValueError("Lead email is suppressed.")
    if lead.organisation_id != sequence.organisation_id:
        raise ValueError("Lead must belong to the same organisation.")

    existing = SequenceEnrollment.objects.filter(
        sequence=sequence, lead=lead
    ).first()
    if existing:
        if existing.status == SequenceEnrollment.Status.ACTIVE:
            return existing
        raise ValueError("Lead was already enrolled in this sequence.")

    first_step = sequence.steps.order_by("position").first()
    now = timezone.now()
    enrollment = SequenceEnrollment.objects.create(
        sequence=sequence,
        lead=lead,
        status=SequenceEnrollment.Status.ACTIVE,
        current_step_position=0,
        next_run_at=now + first_step.delay_timedelta,
        enrolled_category_id=lead.category_id,
    )
    record_lead_activity(
        lead,
        kind=LeadActivity.Kind.CUSTOM,
        summary=f"Enrolled in sequence “{sequence.name}”",
        actor=actor,
    )
    return enrollment


def enroll_list(sequence: EmailSequence, contact_list, *, actor=None) -> int:
    count = 0
    for lead in resolve_list_members(contact_list).exclude(email="").iterator():
        try:
            enroll_lead(sequence, lead, actor=actor)
            count += 1
        except ValueError:
            continue
    return count


def _send_step(
    enrollment: SequenceEnrollment, step: SequenceStep
) -> SequenceStepSend | None:
    lead = enrollment.lead
    if is_email_suppressed(enrollment.sequence.organisation, lead.email):
        _exit_enrollment(enrollment, SequenceEnrollment.ExitReason.UNSUBSCRIBE)
        return None
    context = build_merge_context(
        lead=lead, organisation=enrollment.sequence.organisation
    )
    template = step.template
    outbound = queue_transactional_email(
        to_email=lead.email,
        subject=render_merge(template.subject, context),
        body_text=render_merge(
            template.body_text or template.body_html, context
        ),
        body_html=render_merge(template.body_html, context),
        organisation=enrollment.sequence.organisation,
        track=True,
        respect_suppression=True,
    )
    if outbound.status == OutboundEmail.Status.SUPPRESSED:
        _exit_enrollment(enrollment, SequenceEnrollment.ExitReason.UNSUBSCRIBE)
        return None
    send = SequenceStepSend.objects.create(
        enrollment=enrollment,
        step=step,
        outbound_email=outbound,
    )
    record_lead_activity(
        lead,
        kind=LeadActivity.Kind.CUSTOM,
        summary=(
            f"Sequence “{enrollment.sequence.name}” step {step.position} sent"
        ),
    )
    return send


def advance_enrollment(enrollment: SequenceEnrollment) -> str:
    """
    Process one due enrollment: exit-check, send next step, schedule following.
    Returns a short status string.
    """
    enrollment = (
        SequenceEnrollment.objects.select_related(
            "sequence", "lead", "sequence__organisation"
        ).get(pk=enrollment.pk)
    )
    if enrollment.status != SequenceEnrollment.Status.ACTIVE:
        return enrollment.status

    reason = check_exit_rules(enrollment)
    if reason:
        _exit_enrollment(enrollment, reason)
        return f"exited:{reason}"

    next_position = enrollment.current_step_position + 1
    step = (
        SequenceStep.objects.filter(
            sequence=enrollment.sequence, position=next_position
        )
        .select_related("template")
        .first()
    )
    if step is None:
        enrollment.status = SequenceEnrollment.Status.COMPLETED
        enrollment.exit_reason = SequenceEnrollment.ExitReason.COMPLETED
        enrollment.completed_at = timezone.now()
        enrollment.next_run_at = None
        enrollment.save(
            update_fields=[
                "status",
                "exit_reason",
                "completed_at",
                "next_run_at",
            ]
        )
        return "completed"

    if not SequenceStepSend.objects.filter(
        enrollment=enrollment, step=step
    ).exists():
        sent = _send_step(enrollment, step)
        enrollment.refresh_from_db()
        if sent is None or enrollment.status != SequenceEnrollment.Status.ACTIVE:
            return f"exited:{enrollment.exit_reason or 'unsubscribe'}"
    enrollment.current_step_position = step.position

    following = SequenceStep.objects.filter(
        sequence=enrollment.sequence, position=step.position + 1
    ).first()
    if following is None:
        enrollment.status = SequenceEnrollment.Status.COMPLETED
        enrollment.exit_reason = SequenceEnrollment.ExitReason.COMPLETED
        enrollment.completed_at = timezone.now()
        enrollment.next_run_at = None
        enrollment.save(
            update_fields=[
                "status",
                "exit_reason",
                "completed_at",
                "next_run_at",
                "current_step_position",
            ]
        )
        return "completed"

    enrollment.next_run_at = timezone.now() + following.delay_timedelta
    enrollment.status = SequenceEnrollment.Status.ACTIVE
    enrollment.save(
        update_fields=["current_step_position", "next_run_at", "status"]
    )
    return f"sent_step:{step.position}"


def advance_due_enrollments(*, limit: int = 100) -> dict:
    """Advance active enrollments whose next_run_at is due."""
    now = timezone.now()
    due = list(
        SequenceEnrollment.objects.filter(
            status=SequenceEnrollment.Status.ACTIVE,
            next_run_at__lte=now,
        ).order_by("next_run_at")[:limit]
    )
    results = {"processed": 0, "sent": 0, "exited": 0, "completed": 0}
    for enrollment in due:
        results["processed"] += 1
        outcome = advance_enrollment(enrollment)
        if outcome.startswith("sent_step"):
            results["sent"] += 1
        elif outcome.startswith("exited"):
            results["exited"] += 1
        elif outcome == "completed":
            results["completed"] += 1
    return results


def cancel_enrollment(
    enrollment: SequenceEnrollment,
) -> SequenceEnrollment:
    if enrollment.status != SequenceEnrollment.Status.ACTIVE:
        return enrollment
    enrollment.status = SequenceEnrollment.Status.CANCELLED
    enrollment.exit_reason = SequenceEnrollment.ExitReason.CANCELLED
    enrollment.completed_at = timezone.now()
    enrollment.next_run_at = None
    enrollment.save(
        update_fields=["status", "exit_reason", "completed_at", "next_run_at"]
    )
    record_lead_activity(
        enrollment.lead,
        kind=LeadActivity.Kind.CUSTOM,
        summary=f"Cancelled sequence “{enrollment.sequence.name}”",
    )
    return enrollment


def activate_sequence(sequence: EmailSequence) -> EmailSequence:
    if not sequence.steps.exists():
        raise ValueError("Add at least one step before activating.")
    sequence.status = EmailSequence.Status.ACTIVE
    sequence.save(update_fields=["status", "updated_at"])
    return sequence
