from django.contrib import admin

from notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "kind",
        "recipient",
        "organisation",
        "read_at",
        "created_at",
    )
    list_filter = ("kind",)
    search_fields = ("title", "recipient__username", "organisation__name")
    raw_id_fields = ("organisation", "recipient")
    readonly_fields = ("created_at",)
