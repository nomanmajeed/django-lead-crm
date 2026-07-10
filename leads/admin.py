from django.contrib import admin

from .models import (
    Agent,
    Category,
    ContactList,
    ContactListMembership,
    Invite,
    Lead,
    LeadActivity,
    LeadNote,
    LeadTask,
    Membership,
    Organisation,
    User,
)


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "plan",
        "owner",
        "stripe_customer_id",
        "auto_assign_enabled",
        "timezone",
        "created_at",
    )
    list_filter = ("plan", "timezone", "auto_assign_enabled")
    search_fields = (
        "name",
        "slug",
        "owner__username",
        "owner__email",
        "stripe_customer_id",
    )
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


@admin.register(Invite)
class InviteAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "organisation",
        "role",
        "created_at",
        "expires_at",
        "accepted_at",
        "revoked_at",
    )
    list_filter = ("role",)
    search_fields = ("email", "organisation__name", "token")
    raw_id_fields = ("organisation", "invited_by")
    readonly_fields = ("token", "created_at", "accepted_at", "revoked_at")


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "is_organisor", "is_agent", "is_staff")
    list_filter = ("is_organisor", "is_agent", "is_staff")
    search_fields = ("username", "email")


@admin.register(LeadNote)
class LeadNoteAdmin(admin.ModelAdmin):
    list_display = ("lead", "author", "created_at")
    raw_id_fields = ("lead", "author")


@admin.register(LeadTask)
class LeadTaskAdmin(admin.ModelAdmin):
    list_display = ("title", "lead", "due_at", "completed_at", "created_by")
    raw_id_fields = ("lead", "created_by")


@admin.register(LeadActivity)
class LeadActivityAdmin(admin.ModelAdmin):
    list_display = ("summary", "kind", "lead", "actor", "created_at")
    list_filter = ("kind",)
    raw_id_fields = ("lead", "actor")


@admin.register(ContactList)
class ContactListAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "organisation", "updated_at")
    list_filter = ("kind",)
    search_fields = ("name", "organisation__name")
    raw_id_fields = ("organisation",)


@admin.register(ContactListMembership)
class ContactListMembershipAdmin(admin.ModelAdmin):
    list_display = ("contact_list", "lead", "added_at")
    raw_id_fields = ("contact_list", "lead")


admin.site.register(Agent)
admin.site.register(Category)
admin.site.register(Lead)
