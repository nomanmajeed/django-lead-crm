from django.contrib import admin

from public_api.models import APIToken


@admin.register(APIToken)
class APITokenAdmin(admin.ModelAdmin):
    list_display = ("name", "prefix", "organisation", "revoked_at", "last_used_at")
    list_filter = ("revoked_at",)
    search_fields = ("name", "prefix", "organisation__name")
    readonly_fields = ("token_hash", "prefix", "created_at", "last_used_at")
    raw_id_fields = ("organisation", "created_by")
