from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from agents.mixins import OrganisorAndLoginRequiredMixin
from capture.forms import CaptureFormBuilder
from capture.models import LeadCaptureForm
from capture.service import (
    DynamicCaptureForm,
    check_rate_limit,
    create_lead_from_capture,
    increment_rate_limit,
)


def _client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class PublicCaptureView(View):
    def _form(self, request, public_key):
        capture_form = get_object_or_404(
            LeadCaptureForm.objects.select_related(
                "organisation", "auto_sequence"
            ),
            public_key=public_key,
            is_active=True,
        )
        return capture_form

    def get(self, request, public_key):
        capture_form = self._form(request, public_key)
        return render(
            request,
            "capture/public_form.html",
            {
                "capture_form": capture_form,
                "form": DynamicCaptureForm(capture_form),
                "embed": request.GET.get("embed") == "1",
            },
        )

    def post(self, request, public_key):
        capture_form = self._form(request, public_key)
        ip = _client_ip(request)
        if not check_rate_limit(capture_form, ip):
            return HttpResponseForbidden("Too many submissions. Try again later.")
        form = DynamicCaptureForm(capture_form, request.POST)
        if not form.is_valid():
            return render(
                request,
                "capture/public_form.html",
                {
                    "capture_form": capture_form,
                    "form": form,
                    "embed": request.GET.get("embed") == "1",
                },
                status=400,
            )
        create_lead_from_capture(capture_form, form.cleaned_data)
        increment_rate_limit(capture_form, ip)
        return render(
            request,
            "capture/thank_you.html",
            {"capture_form": capture_form, "embed": request.GET.get("embed") == "1"},
        )


class CaptureFormIndexView(OrganisorAndLoginRequiredMixin, View):
    def get(self, request):
        forms = LeadCaptureForm.objects.filter(
            organisation=request.organisation
        ).select_related("auto_sequence")
        return render(
            request,
            "app/capture/index.html",
            {"topbar_title": "Capture forms", "forms": forms},
        )


class CaptureFormCreateView(OrganisorAndLoginRequiredMixin, View):
    def get(self, request):
        return render(
            request,
            "app/capture/form.html",
            {
                "topbar_title": "New capture form",
                "heading": "Create capture form",
                "form": CaptureFormBuilder(organisation=request.organisation),
            },
        )

    def post(self, request):
        form = CaptureFormBuilder(
            request.POST, organisation=request.organisation
        )
        if form.is_valid():
            capture = form.save()
            messages.success(request, f"Capture form “{capture.name}” created.")
            return redirect("capture_detail", pk=capture.pk)
        return render(
            request,
            "app/capture/form.html",
            {
                "topbar_title": "New capture form",
                "heading": "Create capture form",
                "form": form,
            },
        )


class CaptureFormDetailView(OrganisorAndLoginRequiredMixin, View):
    def _get(self, request, pk):
        return get_object_or_404(
            LeadCaptureForm,
            pk=pk,
            organisation=request.organisation,
        )

    def get(self, request, pk):
        capture = self._get(request, pk)
        public_url = request.build_absolute_uri(capture.public_path())
        embed_url = f"{public_url}?embed=1"
        return render(
            request,
            "app/capture/detail.html",
            {
                "topbar_title": capture.name,
                "capture": capture,
                "public_url": public_url,
                "embed_url": embed_url,
                "form": CaptureFormBuilder(
                    instance=capture, organisation=request.organisation
                ),
            },
        )

    def post(self, request, pk):
        capture = self._get(request, pk)
        form = CaptureFormBuilder(
            request.POST,
            instance=capture,
            organisation=request.organisation,
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Capture form updated.")
            return redirect("capture_detail", pk=pk)
        public_url = request.build_absolute_uri(capture.public_path())
        return render(
            request,
            "app/capture/detail.html",
            {
                "topbar_title": capture.name,
                "capture": capture,
                "public_url": public_url,
                "embed_url": f"{public_url}?embed=1",
                "form": form,
            },
        )
