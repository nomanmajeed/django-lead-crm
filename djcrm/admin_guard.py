"""Restrict Django admin to staff users; hide when disabled."""

from django.http import HttpResponseForbidden, HttpResponseNotFound


class AdminGuardMiddleware:
    """Block admin for anonymous/non-staff users; hide admin when disabled."""

    def __init__(self, get_response):
        self.get_response = get_response

    def _is_public_admin_path(self, path: str) -> bool:
        return path.startswith("/admin/login") or path.startswith("/admin/logout")

    def __call__(self, request):
        if not request.path.startswith("/admin/"):
            return self.get_response(request)

        from django.conf import settings

        if not getattr(settings, "DJANGO_ADMIN_ENABLED", True):
            return HttpResponseNotFound()

        if self._is_public_admin_path(request.path):
            return self.get_response(request)

        user = getattr(request, "user", None)
        if not user or not user.is_authenticated or not user.is_staff:
            if user and user.is_authenticated:
                return HttpResponseForbidden("Admin access requires a staff account.")
            return HttpResponseNotFound()

        return self.get_response(request)
