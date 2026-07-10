from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import post_save
from django.utils.text import slugify


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


class Agent(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Agent"
        verbose_name_plural = "Agents"

    def __str__(self):
        return self.user.username


class Category(models.Model):
    name = models.CharField(max_length=30)  # New, Contacted, Converted, Unconverted
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE)

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

    class Meta:
        verbose_name = "Lead"
        verbose_name_plural = "Leads"

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


def _unique_org_slug(base: str) -> str:
    slug = base or "organisation"
    candidate = slug
    index = 1
    while Organisation.objects.filter(slug=candidate).exists():
        candidate = f"{slug}-{index}"
        index += 1
    return candidate


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
