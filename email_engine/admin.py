from django.contrib import admin

from email_engine.models import (
    Campaign,
    CampaignRecipient,
    EmailDeliveryEvent,
    EmailSequence,
    EmailSuppression,
    EmailTemplate,
    OutboundEmail,
    SequenceEnrollment,
    SequenceStep,
    SequenceStepSend,
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


@admin.register(EmailSuppression)
class EmailSuppressionAdmin(admin.ModelAdmin):
    list_display = ("email", "organisation", "reason", "created_at")
    search_fields = ("email", "organisation__name")
    raw_id_fields = ("organisation",)


class SequenceStepInline(admin.TabularInline):
    model = SequenceStep
    extra = 0
    raw_id_fields = ("template",)


@admin.register(EmailSequence)
class EmailSequenceAdmin(admin.ModelAdmin):
    list_display = ("name", "organisation", "status", "updated_at")
    list_filter = ("status",)
    search_fields = ("name", "organisation__name")
    raw_id_fields = ("organisation", "created_by")
    inlines = [SequenceStepInline]


@admin.register(SequenceEnrollment)
class SequenceEnrollmentAdmin(admin.ModelAdmin):
    list_display = (
        "sequence",
        "lead",
        "status",
        "current_step_position",
        "next_run_at",
        "exit_reason",
    )
    list_filter = ("status", "exit_reason")
    raw_id_fields = ("sequence", "lead")


@admin.register(SequenceStepSend)
class SequenceStepSendAdmin(admin.ModelAdmin):
    list_display = ("enrollment", "step", "sent_at")
    raw_id_fields = ("enrollment", "step", "outbound_email")
