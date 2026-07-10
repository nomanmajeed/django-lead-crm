from leads.permissions import (
    user_can_manage_organisation,
    user_is_agent_member,
    user_is_org_owner,
)


def tenant(request):
    user = getattr(request, "user", None)
    org = getattr(request, "organisation", None)
    return {
        "current_organisation": org,
        "can_manage": user_can_manage_organisation(user) if user else False,
        "is_agent_member": user_is_agent_member(user) if user else False,
        "is_org_owner": user_is_org_owner(user, org) if user else False,
        "product_space": getattr(request, "product_space", "marketing"),
    }
