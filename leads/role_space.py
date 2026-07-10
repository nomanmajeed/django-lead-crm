"""Keep agents in /agent/* and organisers in /app/*."""

from django.shortcuts import redirect

from leads.permissions import user_can_manage_organisation, user_is_agent_member


class RoleSpaceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.product_space = "marketing"
        user = getattr(request, "user", None)
        path = request.path

        if path.startswith("/app/"):
            request.product_space = "app"
        elif path.startswith("/agent/"):
            request.product_space = "agent"

        if user is not None and user.is_authenticated:
            can_manage = user_can_manage_organisation(user)
            is_agent = user_is_agent_member(user)

            if path.startswith("/app/") and not can_manage:
                if is_agent:
                    return redirect("agent_home")
                return redirect("landing_page")

            if path.startswith("/agent/") and not is_agent:
                if can_manage:
                    return redirect("app_home")
                return redirect("landing_page")

        return self.get_response(request)
