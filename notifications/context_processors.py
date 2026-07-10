from notifications.models import Notification


def notifications_badge(request):
    user = getattr(request, "user", None)
    org = getattr(request, "organisation", None)
    unread = 0
    if user and getattr(user, "is_authenticated", False) and org:
        unread = Notification.objects.filter(
            organisation=org,
            recipient=user,
            read_at__isnull=True,
        ).count()
    return {"notification_unread_count": unread}
