"""Public tracking pixel, click redirect, and unsubscribe endpoints."""

from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from email_engine.models import OutboundEmail
from email_engine.tracking import (
    PIXEL_GIF,
    process_unsubscribe,
    record_click,
    record_open,
    safe_redirect_url,
)


@require_GET
def track_open(request, token):
    outbound = get_object_or_404(OutboundEmail, tracking_token=token)
    record_open(outbound)
    return HttpResponse(PIXEL_GIF, content_type="image/gif")


@require_GET
def track_click(request, token):
    outbound = get_object_or_404(OutboundEmail, tracking_token=token)
    target = safe_redirect_url(request.GET.get("u", ""))
    if target == "/":
        return HttpResponseBadRequest("Invalid URL")
    record_click(outbound, target)
    return HttpResponseRedirect(target)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def unsubscribe(request, token):
    outbound = get_object_or_404(OutboundEmail, tracking_token=token)
    if request.method == "POST":
        process_unsubscribe(outbound)
        return render(
            request,
            "email/unsubscribed.html",
            {"email": outbound.to_email, "organisation": outbound.organisation},
        )
    return render(
        request,
        "email/unsubscribe_confirm.html",
        {"email": outbound.to_email, "organisation": outbound.organisation},
    )
