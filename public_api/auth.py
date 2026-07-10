"""Bearer token authentication for org-scoped JSON API."""

from __future__ import annotations

import json

from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from public_api.models import APIToken


class APIError(Exception):
    def __init__(self, message: str, *, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def parse_json_body(request) -> dict:
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise APIError("Invalid JSON body.", status=400) from exc


def json_error(message: str, *, status: int = 400) -> JsonResponse:
    return JsonResponse({"error": message}, status=status)


def authenticate_request(request) -> APIToken:
    header = request.META.get("HTTP_AUTHORIZATION", "")
    if not header.startswith("Bearer "):
        raise APIError("Missing Bearer token.", status=401)
    raw = header[7:].strip()
    token = APIToken.resolve(raw)
    if token is None:
        raise APIError("Invalid or revoked API token.", status=401)
    token.last_used_at = timezone.now()
    token.save(update_fields=["last_used_at"])
    request.api_token = token
    request.api_organisation = token.organisation
    return token


class TokenAuthView(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        try:
            authenticate_request(request)
        except APIError as exc:
            return json_error(exc.message, status=exc.status)
        try:
            return super().dispatch(request, *args, **kwargs)
        except APIError as exc:
            return json_error(exc.message, status=exc.status)
