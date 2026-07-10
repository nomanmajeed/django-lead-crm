"""Tenant / organisation request resolution."""

SESSION_ORG_KEY = "current_organisation_id"


class TenantMiddleware:
    """
    Attach ``request.organisation`` for authenticated users.

    Resolution order:
    1. Session ``current_organisation_id`` if the user is a member
    2. Fallback to the user's primary organisation (membership / ownership)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.organisation = None
        user = getattr(request, "user", None)

        if user is not None and user.is_authenticated:
            from leads.models import Organisation
            from leads.permissions import get_user_organisation

            organisation = None
            org_id = request.session.get(SESSION_ORG_KEY)
            if org_id:
                organisation = (
                    Organisation.objects.filter(
                        pk=org_id,
                        memberships__user=user,
                    )
                    .distinct()
                    .first()
                )

            if organisation is None:
                organisation = get_user_organisation(user)
                if organisation is not None:
                    request.session[SESSION_ORG_KEY] = organisation.pk
                elif SESSION_ORG_KEY in request.session:
                    del request.session[SESSION_ORG_KEY]

            request.organisation = organisation

        return self.get_response(request)
