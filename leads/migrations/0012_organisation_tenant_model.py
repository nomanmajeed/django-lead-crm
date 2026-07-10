import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models
from django.utils.text import slugify


def populate_organisation_fields(apps, schema_editor):
    UserProfile = apps.get_model("leads", "UserProfile")
    used_slugs = set(
        UserProfile.objects.exclude(slug__isnull=True)
        .exclude(slug="")
        .values_list("slug", flat=True)
    )

    for profile in UserProfile.objects.select_related("user").all():
        username = profile.user.username
        base = slugify(username) or f"user-{profile.user_id}"
        slug = base
        index = 1
        while slug in used_slugs:
            slug = f"{base}-{index}"
            index += 1
        used_slugs.add(slug)

        profile.name = f"{username}'s organisation"
        profile.slug = slug
        profile.plan = "free"
        profile.timezone = "UTC"
        profile.primary_color = "#0F766E"
        profile.save(
            update_fields=["name", "slug", "plan", "timezone", "primary_color"]
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0011_auto_20210216_1557"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="agent",
            options={"verbose_name": "Agent", "verbose_name_plural": "Agents"},
        ),
        migrations.AlterModelOptions(
            name="category",
            options={"verbose_name": "Category", "verbose_name_plural": "Categories"},
        ),
        migrations.AlterModelOptions(
            name="lead",
            options={"verbose_name": "Lead", "verbose_name_plural": "Leads"},
        ),
        migrations.AlterModelTable(name="agent", table=None),
        migrations.AlterModelTable(name="category", table=None),
        migrations.AlterModelTable(name="lead", table=None),
        migrations.AlterModelTable(name="userprofile", table=None),
        migrations.AddField(
            model_name="userprofile",
            name="name",
            field=models.CharField(max_length=120, null=True),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="slug",
            field=models.SlugField(max_length=140, null=True),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="plan",
            field=models.CharField(
                choices=[
                    ("free", "Free"),
                    ("pro", "Pro"),
                    ("business", "Business"),
                ],
                default="free",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="timezone",
            field=models.CharField(default="UTC", max_length=64),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="primary_color",
            field=models.CharField(blank=True, default="#0F766E", max_length=7),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True, default=django.utils.timezone.now
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="userprofile",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.RunPython(populate_organisation_fields, noop_reverse),
        migrations.AlterField(
            model_name="userprofile",
            name="name",
            field=models.CharField(max_length=120),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="slug",
            field=models.SlugField(max_length=140, unique=True),
        ),
        migrations.RenameModel(old_name="UserProfile", new_name="Organisation"),
        migrations.RenameField(
            model_name="organisation",
            old_name="user",
            new_name="owner",
        ),
        migrations.AlterField(
            model_name="organisation",
            name="owner",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="organisation",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterModelOptions(
            name="organisation",
            options={
                "ordering": ["name"],
                "verbose_name": "Organisation",
                "verbose_name_plural": "Organisations",
            },
        ),
        migrations.AlterField(
            model_name="agent",
            name="organisation",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="leads.organisation",
            ),
        ),
        migrations.AlterField(
            model_name="category",
            name="organisation",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="leads.organisation",
            ),
        ),
        migrations.AlterField(
            model_name="lead",
            name="organisation",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="leads.organisation",
            ),
        ),
    ]
