def tenant(request):
    return {
        "current_organisation": getattr(request, "organisation", None),
    }
