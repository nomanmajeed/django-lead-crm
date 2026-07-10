from django.contrib import admin

from capture.models import LeadCaptureForm


@admin.register(LeadCaptureForm)
class LeadCaptureFormAdmin(admin.ModelAdmin):
    list_display = ("name", "organisation", "is_active", "public_key", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "organisation__name")
    readonly_fields = ("public_key", "created_at", "updated_at")
    raw_id_fields = ("organisation", "auto_sequence")
