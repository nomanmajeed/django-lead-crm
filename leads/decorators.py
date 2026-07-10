from django.shortcuts import redirect

from leads.permissions import user_can_manage_organisation


def user_is_organisor(f):
    def wrap(request, *args, **kwargs):
        if not user_can_manage_organisation(request.user):
            return redirect("leads:lead_list")
        return f(request, *args, **kwargs)

    wrap.__doc__ = f.__doc__
    wrap.__name__ = f.__name__
    return wrap
