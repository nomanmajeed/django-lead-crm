from django.contrib import admin

from email_engine.models import EmailDeliveryEvent, OutboundEmail


@admin.register(OutboundEmail)
class OutboundEmailAdmin(admin.ModelAdmin):
    list_display = (
        "subject",
        "to_email",
        "provider",
        "status",
        "organisation",
        "created_at",
        "sent_at",
    )
    list_filter = ("provider", "status")
    search_fields = ("to_email", "subject", "provider_message_id")
    readonly_fields = ("created_at", "sent_at")


@admin.register(EmailDeliveryEvent)
class EmailDeliveryEventAdmin(admin.ModelAdmin):
    list_display = (
        "event_type",
        "provider",
        "provider_message_id",
        "outbound_email",
        "created_at",
    )
    list_filter = ("event_type", "provider")
    search_fields = ("provider_message_id",)
