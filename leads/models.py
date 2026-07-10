from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import post_save
from django.utils.text import slugify

from .managers import TenantManager


class User(AbstractUser):
    # Denormalized cache of Membership roles (Membership is source of truth).
    is_organisor = models.BooleanField(default=True)
    is_agent = models.BooleanField(default=False)

    def get_memberships(self):
        return self.memberships.select_related("organisation")

    def membership_for(self, organisation):
        return self.memberships.filter(organisation=organisation).first()


class Organisation(models.Model):
    """Tenant / workspace. Evolved from the former UserProfile model."""

    class Plan(models.TextChoices):
        FREE = "free", "Free"
        PRO = "pro", "Pro"
        BUSINESS = "business", "Business"

    owner = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="owned_organisation",
    )
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    plan = models.CharField(
        max_length=20,
        choices=Plan.choices,
        default=Plan.FREE,
    )
    timezone = models.CharField(max_length=64, default="UTC")
    # Branding hooks (expand later with logo upload, etc.)
    primary_color = models.CharField(max_length=7, blank=True, default="#0F766E")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Organisation"
        verbose_name_plural = "Organisations"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        AGENT = "agent", "Agent"
        VIEWER = "viewer", "Viewer"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Membership"
        verbose_name_plural = "Memberships"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "organisation"],
                name="uniq_membership_user_organisation",
            )
        ]
        ordering = ["organisation__name", "user__username"]

    def __str__(self):
        return f"{self.user} · {self.organisation} ({self.role})"


class Invite(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        AGENT = "agent", "Agent"
        VIEWER = "viewer", "Viewer"

    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.CASCADE,
        related_name="invites",
    )
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.AGENT)
    token = models.CharField(max_length=64, unique=True, db_index=True)
    invited_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_invites",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Invite"
        verbose_name_plural = "Invites"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.email} → {self.organisation} ({self.role})"

    @property
    def is_pending(self):
        return self.accepted_at is None and self.revoked_at is None

    def is_usable(self):
        from django.utils import timezone

        return self.is_pending and self.expires_at > timezone.now()


class Agent(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)

    objects = TenantManager()

    class Meta:
        verbose_name = "Agent"
        verbose_name_plural = "Agents"

    def __str__(self):
        return self.user.username


class Category(models.Model):
    name = models.CharField(max_length=30)  # New, Contacted, Converted, Unconverted
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)

    objects = TenantManager()

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Lead(models.Model):
    first_name = models.CharField(max_length=20)
    last_name = models.CharField(max_length=20)
    age = models.IntegerField(default=0)
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    agent = models.ForeignKey(
        Agent, null=True, blank=True, on_delete=models.SET_NULL
    )
    category = models.ForeignKey(
        Category, null=True, blank=True, on_delete=models.CASCADE
    )
    description = models.TextField()
    date_added = models.DateTimeField(auto_now_add=True)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField()
    custom_fields = models.JSONField(default=dict, blank=True)

    objects = TenantManager()

    class Meta:
        verbose_name = "Lead"
        verbose_name_plural = "Leads"

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class LeadNote(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="lead_notes")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Note on {self.lead_id} by {self.author_id}"


class LeadTask(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=200)
    due_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="created_lead_tasks"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["completed_at", "due_at", "-created_at"]

    def __str__(self):
        return self.title

    @property
    def is_complete(self):
        return self.completed_at is not None


class LeadActivity(models.Model):
    class Kind(models.TextChoices):
        NOTE = "note", "Note"
        TASK_CREATED = "task_created", "Task created"
        TASK_COMPLETED = "task_completed", "Task completed"
        STATUS = "status", "Status change"
        ASSIGNMENT = "assignment", "Assignment"
        CUSTOM = "custom", "Custom field"

    lead = models.ForeignKey(
        Lead, on_delete=models.CASCADE, related_name="activities"
    )
    actor = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lead_activities",
    )
    kind = models.CharField(max_length=32, choices=Kind.choices)
    summary = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Lead activities"

    def __str__(self):
        return self.summary


def record_lead_activity(lead, *, kind, summary, actor=None):
    return LeadActivity.objects.create(
        lead=lead,
        actor=actor,
        kind=kind,
        summary=summary,
    )


def unique_org_slug(base: str, exclude_pk=None) -> str:
    slug = base or "organisation"
    candidate = slug
    index = 1
    while True:
        qs = Organisation.objects.filter(slug=candidate)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        if not qs.exists():
            return candidate
        candidate = f"{slug}-{index}"
        index += 1


def _unique_org_slug(base: str) -> str:
    return unique_org_slug(base)


def post_user_created_signal(sender, instance, created, **kwargs):
    """New organisers get an Organisation + Owner membership. Agents do not."""
    if not created or not instance.is_organisor:
        return

    base_slug = slugify(instance.username) or f"user-{instance.pk}"
    organisation = Organisation.objects.create(
        owner=instance,
        name=f"{instance.get_username()}'s organisation",
        slug=_unique_org_slug(base_slug),
    )
    Membership.objects.create(
        user=instance,
        organisation=organisation,
        role=Membership.Role.OWNER,
    )


def sync_user_role_flags(sender, instance, **kwargs):
    """Keep denormalized User.is_organisor / is_agent in sync with Membership."""
    user = instance.user
    roles = set(
        Membership.objects.filter(user=user).values_list("role", flat=True)
    )
    is_organisor = bool(
        roles
        & {
            Membership.Role.OWNER,
            Membership.Role.ADMIN,
        }
    )
    is_agent = Membership.Role.AGENT in roles
    if user.is_organisor != is_organisor or user.is_agent != is_agent:
        User.objects.filter(pk=user.pk).update(
            is_organisor=is_organisor,
            is_agent=is_agent,
        )


post_save.connect(post_user_created_signal, sender=User)
post_save.connect(sync_user_role_flags, sender=Membership)
