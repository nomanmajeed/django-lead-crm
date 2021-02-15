from django.shortcuts import redirect


def user_is_organisor(f):
    def wrap(request, *args, **kwargs):
        # this check the session if userid key exist, if not it will redirect to login page
        if not request.user.is_organisor:
            return redirect("leads:lead_list")
        return f(request, *args, **kwargs)

    wrap.__doc__ = f.__doc__
    wrap.__name__ = f.__name__
    return wrap

