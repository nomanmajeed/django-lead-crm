from django.contrib import admin

from .models import Agent, Category, Lead, Membership, Organisation, User


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "plan", "owner", "timezone", "created_at")
    list_filter = ("plan", "timezone")
    search_fields = ("name", "slug", "owner__username", "owner__email")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organisation", "role", "created_at")
    list_filter = ("role",)
    search_fields = (
        "user__username",
        "user__email",
        "organisation__name",
        "organisation__slug",
    )
    raw_id_fields = ("user", "organisation")


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "is_organisor", "is_agent", "is_staff")
    list_filter = ("is_organisor", "is_agent", "is_staff")
    search_fields = ("username", "email")


admin.site.register(Agent)
admin.site.register(Category)
admin.site.register(Lead)
