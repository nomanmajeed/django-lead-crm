from django.contrib import admin

from .models import Agent, Category, Lead, Organisation, User


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "plan", "owner", "timezone", "created_at")
    list_filter = ("plan", "timezone")
    search_fields = ("name", "slug", "owner__username", "owner__email")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")


admin.site.register(User)
admin.site.register(Agent)
admin.site.register(Category)
admin.site.register(Lead)
