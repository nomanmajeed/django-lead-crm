from django.contrib import admin

from audit.models import AuditEntry


@admin.register(AuditEntry)
class AuditEntryAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "organisation",
        "actor",
        "action",
        "object_type",
        "object_repr",
        "summary",
    )
    list_filter = ("object_type", "action", "organisation")
    search_fields = ("summary", "object_repr", "actor__username")
    readonly_fields = (
        "organisation",
        "actor",
        "action",
        "object_type",
        "object_id",
        "object_repr",
        "summary",
        "metadata",
        "created_at",
    )
    raw_id_fields = ("organisation", "actor")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
