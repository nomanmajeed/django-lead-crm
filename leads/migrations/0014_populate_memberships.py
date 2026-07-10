from django.db import migrations


def migrate_roles_to_memberships(apps, schema_editor):
    Organisation = apps.get_model("leads", "Organisation")
    Agent = apps.get_model("leads", "Agent")
    Membership = apps.get_model("leads", "Membership")
    User = apps.get_model("leads", "User")

    for organisation in Organisation.objects.select_related("owner"):
        Membership.objects.get_or_create(
            user=organisation.owner,
            organisation=organisation,
            defaults={"role": "owner"},
        )
        User.objects.filter(pk=organisation.owner_id).update(
            is_organisor=True,
            is_agent=False,
        )

    for agent in Agent.objects.select_related("user", "organisation"):
        Membership.objects.update_or_create(
            user=agent.user,
            organisation=agent.organisation,
            defaults={"role": "agent"},
        )
        User.objects.filter(pk=agent.user_id).update(
            is_organisor=False,
            is_agent=True,
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0013_membership_and_roles"),
    ]

    operations = [
        migrations.RunPython(migrate_roles_to_memberships, noop_reverse),
    ]
