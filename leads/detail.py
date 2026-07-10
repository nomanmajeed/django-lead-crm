"""Lead detail 360° helpers — notes, tasks, timeline, light custom fields."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from leads.models import (
    LeadActivity,
    LeadNote,
    LeadTask,
    record_lead_activity,
)
from leads.views import _agent_scoped_leads, _space_template


@login_required
def lead_detail(request, pk):
    lead = get_object_or_404(
        _agent_scoped_leads(request).select_related("category", "agent", "agent__user"),
        pk=pk,
    )

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add_note":
            body = (request.POST.get("body") or "").strip()
            if body:
                LeadNote.objects.create(lead=lead, author=request.user, body=body)
                record_lead_activity(
                    lead,
                    kind=LeadActivity.Kind.NOTE,
                    summary=f"Note added by {request.user.username}",
                    actor=request.user,
                )
                messages.success(request, "Note added.")
            else:
                messages.error(request, "Note cannot be empty.")
        elif action == "add_task":
            title = (request.POST.get("title") or "").strip()
            due_raw = (request.POST.get("due_at") or "").strip()
            due_at = None
            if due_raw:
                due_at = parse_datetime(due_raw.replace("T", " "))
                if due_at is None:
                    try:
                        due_at = timezone.datetime.fromisoformat(due_raw)
                        if timezone.is_naive(due_at):
                            due_at = timezone.make_aware(
                                due_at, timezone.get_current_timezone()
                            )
                    except ValueError:
                        due_at = None
            if title:
                LeadTask.objects.create(
                    lead=lead,
                    title=title,
                    due_at=due_at,
                    created_by=request.user,
                )
                record_lead_activity(
                    lead,
                    kind=LeadActivity.Kind.TASK_CREATED,
                    summary=f"Task created: {title}",
                    actor=request.user,
                )
                messages.success(request, "Task created.")
            else:
                messages.error(request, "Task title is required.")
        elif action == "complete_task":
            task = get_object_or_404(LeadTask, pk=request.POST.get("task_id"), lead=lead)
            if task.completed_at is None:
                task.completed_at = timezone.now()
                task.save(update_fields=["completed_at"])
                record_lead_activity(
                    lead,
                    kind=LeadActivity.Kind.TASK_COMPLETED,
                    summary=f"Task completed: {task.title}",
                    actor=request.user,
                )
                messages.success(request, "Task completed.")
        elif action == "save_custom_fields":
            company = (request.POST.get("company") or "").strip()
            source = (request.POST.get("source") or "").strip()
            fields = dict(lead.custom_fields or {})
            fields["company"] = company
            fields["source"] = source
            lead.custom_fields = fields
            lead.save(update_fields=["custom_fields"])
            record_lead_activity(
                lead,
                kind=LeadActivity.Kind.CUSTOM,
                summary="Custom fields updated",
                actor=request.user,
            )
            messages.success(request, "Custom fields saved.")
        return redirect(request.path)

    open_tasks = lead.tasks.filter(completed_at__isnull=True)
    done_tasks = lead.tasks.filter(completed_at__isnull=False)[:5]
    timeline = lead.activities.select_related("actor")[:40]
    custom = lead.custom_fields or {}

    return render(
        request,
        _space_template(
            request, "leads/lead_detail.html", "agent/lead_detail.html"
        ),
        {
            "lead": lead,
            "topbar_title": f"{lead.first_name} {lead.last_name}",
            "notes": lead.notes.select_related("author")[:20],
            "open_tasks": open_tasks,
            "done_tasks": done_tasks,
            "timeline": timeline,
            "custom_company": custom.get("company", ""),
            "custom_source": custom.get("source", ""),
            "is_agent_space": getattr(request, "product_space", None) == "agent",
        },
    )
