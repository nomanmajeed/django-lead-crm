"""Security middleware: rate limits and response headers."""

from django.conf import settings

from security.rate_limit import check_path_rate_limit


class RateLimitMiddleware:
    """Rate-limit auth POSTs and webhook endpoints by client IP."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST":
            path = request.path
            if path == "/login/":
                blocked = check_path_rate_limit(
                    request,
                    bucket="auth:login",
                    limit_setting="AUTH_LOGIN_RATE_LIMIT",
                    window_setting="AUTH_LOGIN_RATE_WINDOW",
                )
                if blocked:
                    return blocked
            elif path == "/signup/":
                blocked = check_path_rate_limit(
                    request,
                    bucket="auth:signup",
                    limit_setting="AUTH_SIGNUP_RATE_LIMIT",
                    window_setting="AUTH_SIGNUP_RATE_WINDOW",
                )
                if blocked:
                    return blocked
            elif path == "/reset-password/":
                blocked = check_path_rate_limit(
                    request,
                    bucket="auth:reset",
                    limit_setting="AUTH_RESET_RATE_LIMIT",
                    window_setting="AUTH_RESET_RATE_WINDOW",
                )
                if blocked:
                    return blocked
            elif path.startswith("/webhooks/"):
                blocked = check_path_rate_limit(
                    request,
                    bucket="webhook",
                    limit_setting="WEBHOOK_RATE_LIMIT",
                    window_setting="WEBHOOK_RATE_WINDOW",
                )
                if blocked:
                    return blocked
        return self.get_response(request)


class SecurityHeadersMiddleware:
    """Baseline security headers including a conservative CSP."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not getattr(settings, "SECURITY_HEADERS_ENABLED", True):
            return response
        csp = getattr(
            settings,
            "CONTENT_SECURITY_POLICY",
            (
                "default-src 'self'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data:; "
                "frame-ancestors 'self'; "
                "base-uri 'self'; "
                "form-action 'self'"
            ),
        )
        response.headers.setdefault("Content-Security-Policy", csp)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response
