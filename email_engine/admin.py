from django.contrib import admin

from email_engine.models import (
    Campaign,
    CampaignRecipient,
    EmailDeliveryEvent,
    EmailTemplate,
    OutboundEmail,
)


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


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "organisation", "subject", "updated_at")
    search_fields = ("name", "subject", "organisation__name")
    raw_id_fields = ("organisation",)


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "organisation",
        "status",
        "contact_list",
        "template",
        "scheduled_at",
        "updated_at",
    )
    list_filter = ("status",)
    search_fields = ("name", "organisation__name")
    raw_id_fields = ("organisation", "contact_list", "template", "created_by")


@admin.register(CampaignRecipient)
class CampaignRecipientAdmin(admin.ModelAdmin):
    list_display = ("campaign", "lead", "status", "updated_at")
    list_filter = ("status",)
    raw_id_fields = ("campaign", "lead", "outbound_email")
