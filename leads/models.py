from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import post_save
from django.utils.text import slugify


class User(AbstractUser):
    is_organisor = models.BooleanField(default=True)
    is_agent = models.BooleanField(default=False)


class Organisation(models.Model):
    """Tenant / workspace. Evolved from the former UserProfile model."""

    class Plan(models.TextChoices):
        FREE = "free", "Free"
        PRO = "pro", "Pro"
        BUSINESS = "business", "Business"

    owner = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="organisation",
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
    if not created:
        return
    base_slug = slugify(instance.username) or f"user-{instance.pk}"
    Organisation.objects.create(
        owner=instance,
        name=f"{instance.get_username()}'s organisation",
        slug=_unique_org_slug(base_slug),
    )


post_save.connect(post_user_created_signal, sender=User)
