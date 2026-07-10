from leads.permissions import user_can_manage_organisation, user_is_agent_member


def tenant(request):
    user = getattr(request, "user", None)
    return {
        "current_organisation": getattr(request, "organisation", None),
        "can_manage": user_can_manage_organisation(user) if user else False,
        "is_agent_member": user_is_agent_member(user) if user else False,
        "product_space": getattr(request, "product_space", "marketing"),
    }
