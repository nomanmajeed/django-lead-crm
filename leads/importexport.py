"""CSV import (column-mapping wizard) and filtered export for leads."""

import csv
import io

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views import View

from agents.mixins import OrganisorAndLoginRequiredMixin

from leads.models import Lead
from leads.pipeline import filter_pipeline_leads

SESSION_IMPORT_KEY = "lead_import_preview"

# Target fields organisers can map CSV columns onto.
IMPORT_FIELDS = (
    ("first_name", "First name", True),
    ("last_name", "Last name", True),
    ("email", "Email", True),
    ("phone_number", "Phone", True),
    ("age", "Age", False),
    ("description", "Description", False),
)

HEADER_ALIASES = {
    "first_name": {"first_name", "firstname", "first", "first name"},
    "last_name": {"last_name", "lastname", "last", "last name", "surname"},
    "email": {"email", "e-mail", "mail"},
    "phone_number": {"phone_number", "phone", "mobile", "cell", "telephone"},
    "age": {"age"},
    "description": {"description", "notes", "note", "desc"},
}


def _guess_mapping(headers):
    mapping = {}
    normalized = {h: h.strip().lower().replace("-", "_") for h in headers}
    for field, aliases in HEADER_ALIASES.items():
        for header, norm in normalized.items():
            compact = norm.replace(" ", "_")
            if compact in aliases or norm in aliases:
                mapping[field] = header
                break
    return mapping


def _decode_upload(uploaded_file):
    raw = uploaded_file.read()
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _parse_csv_text(text):
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV has no header row.")
    headers = [h.strip() for h in reader.fieldnames if h and h.strip()]
    rows = []
    for row in reader:
        rows.append({(k or "").strip(): (v or "").strip() for k, v in row.items() if k})
    return headers, rows


def _row_to_lead_data(row, mapping):
    data = {}
    errors = []
    for field, _label, required in IMPORT_FIELDS:
        header = mapping.get(field) or ""
        value = row.get(header, "").strip() if header else ""
        if required and not value:
            errors.append(f"Missing {field}")
            continue
        if field == "age":
            if value == "":
                data["age"] = 0
            else:
                try:
                    data["age"] = int(value)
                except ValueError:
                    errors.append("Age must be an integer")
            continue
        if field == "description":
            data["description"] = value or "Imported lead"
            continue
        data[field] = value
    return data, errors


def import_rows(organisation, rows, mapping):
    """Import valid rows; skip bad ones. Returns (created_count, error_rows)."""
    created = 0
    error_rows = []
    for index, row in enumerate(rows, start=2):  # header is line 1
        data, errors = _row_to_lead_data(row, mapping)
        if errors:
            error_rows.append({"line": index, "errors": errors, "row": row})
            continue
        Lead.objects.create(organisation=organisation, agent=None, **data)
        created += 1
    return created, error_rows


class LeadImportView(OrganisorAndLoginRequiredMixin, View):
    """
    Two-step wizard: upload CSV → map columns → import.

    Policy: valid rows are imported; invalid rows are skipped and listed
    in the error report (partial success).
    """

    template_name = "leads/import.html"

    def get(self, request):
        preview = request.session.get(SESSION_IMPORT_KEY)
        return render(
            request,
            self.template_name,
            {
                "topbar_title": "Import leads",
                "preview": preview,
                "import_fields": IMPORT_FIELDS,
                "guessed": _guess_mapping(preview["headers"]) if preview else {},
                "result": None,
            },
        )

    def post(self, request):
        organisation = request.organisation
        action = request.POST.get("action", "upload")

        if action == "cancel":
            request.session.pop(SESSION_IMPORT_KEY, None)
            messages.info(request, "Import cancelled.")
            return redirect("leads:lead_import")

        if action == "upload":
            uploaded = request.FILES.get("csv_file")
            if not uploaded:
                messages.error(request, "Choose a CSV file to upload.")
                return redirect("leads:lead_import")
            try:
                text = _decode_upload(uploaded)
                headers, rows = _parse_csv_text(text)
            except ValueError as exc:
                messages.error(request, str(exc))
                return redirect("leads:lead_import")
            if not rows:
                messages.error(request, "CSV has no data rows.")
                return redirect("leads:lead_import")
            request.session[SESSION_IMPORT_KEY] = {
                "headers": headers,
                "rows": rows,
                "filename": uploaded.name,
            }
            messages.success(
                request,
                f"Loaded {len(rows)} row(s) from {uploaded.name}. Map columns to continue.",
            )
            return redirect("leads:lead_import")

        if action == "import":
            preview = request.session.get(SESSION_IMPORT_KEY)
            if not preview:
                messages.error(request, "Upload a CSV first.")
                return redirect("leads:lead_import")
            mapping = {
                field: request.POST.get(f"map_{field}", "").strip()
                for field, _label, _req in IMPORT_FIELDS
            }
            missing_required = [
                label
                for field, label, required in IMPORT_FIELDS
                if required and not mapping.get(field)
            ]
            if missing_required:
                messages.error(
                    request,
                    "Map required fields: " + ", ".join(missing_required),
                )
                return redirect("leads:lead_import")

            created, error_rows = import_rows(
                organisation, preview["rows"], mapping
            )
            request.session.pop(SESSION_IMPORT_KEY, None)
            return render(
                request,
                self.template_name,
                {
                    "topbar_title": "Import leads",
                    "preview": None,
                    "import_fields": IMPORT_FIELDS,
                    "guessed": {},
                    "result": {
                        "created": created,
                        "errors": error_rows,
                        "skipped": len(error_rows),
                    },
                },
            )

        return redirect("leads:lead_import")


class LeadExportView(OrganisorAndLoginRequiredMixin, View):
    """Export leads matching the same filters as the pipeline view."""

    def get(self, request):
        organisation = request.organisation
        q = request.GET.get("q", "").strip()
        agent_id = request.GET.get("agent", "").strip()
        stage = request.GET.get("stage", "").strip()
        leads = filter_pipeline_leads(
            organisation, q=q, agent_id=agent_id, stage=stage
        )

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="leads-export.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "first_name",
                "last_name",
                "email",
                "phone_number",
                "age",
                "description",
                "stage",
                "agent",
            ]
        )
        for lead in leads:
            writer.writerow(
                [
                    lead.first_name,
                    lead.last_name,
                    lead.email,
                    lead.phone_number,
                    lead.age,
                    lead.description,
                    lead.category.name if lead.category else "",
                    lead.agent.user.username if lead.agent else "",
                ]
            )
        return response
