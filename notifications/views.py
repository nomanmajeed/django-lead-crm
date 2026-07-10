from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from notifications.models import Notification
from notifications.service import mark_all_read, mark_read


class NotificationInboxView(LoginRequiredMixin, View):
    login_url = "login"

    def get(self, request):
        org = request.organisation
        notifications = (
            Notification.objects.filter(
                organisation=org, recipient=request.user
            ).order_by("-created_at")[:100]
            if org
            else Notification.objects.none()
        )
        space = getattr(request, "product_space", "app")
        template = (
            "agent/notifications.html"
            if space == "agent"
            else "app/notifications.html"
        )
        return render(
            request,
            template,
            {
                "topbar_title": "Notifications",
                "notifications": notifications,
            },
        )

    def post(self, request):
        org = request.organisation
        action = request.POST.get("action", "")
        if org and action == "mark_all_read":
            mark_all_read(org, request.user)
        elif org and action == "mark_read":
            note = get_object_or_404(
                Notification,
                pk=request.POST.get("notification_id"),
                organisation=org,
                recipient=request.user,
            )
            mark_read(note)
        return redirect(request.path)
