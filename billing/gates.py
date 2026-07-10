"""View helpers for plan entitlement gates."""

from django.shortcuts import render

from billing.entitlements import EntitlementDenied, require_feature


def feature_or_upgrade(request, feature: str):
    """
    Return None if allowed, or an upgrade-required HttpResponse if blocked.
    """
    try:
        require_feature(request.organisation, feature)
    except EntitlementDenied as exc:
        return render(
            request,
            "app/billing/upgrade_required.html",
            {
                "topbar_title": "Upgrade required",
                "feature_label": feature.replace("_", " "),
                "message": exc.message,
            },
            status=403,
        )
    return None
