from django.shortcuts import redirect

from leads.permissions import user_can_manage_organisation, user_is_agent_member


def user_is_organisor(f):
    def wrap(request, *args, **kwargs):
        if not user_can_manage_organisation(request.user):
            if user_is_agent_member(request.user):
                return redirect("agent_home")
            return redirect("landing_page")
        return f(request, *args, **kwargs)

    wrap.__doc__ = f.__doc__
    wrap.__name__ = f.__name__
    return wrap
