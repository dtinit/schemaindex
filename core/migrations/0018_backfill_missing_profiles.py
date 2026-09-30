# Backfills Profiles for Users created while the post_save receiver in
# core/signals.py was not registered (it was unintentionally disconnected
# from CoreConfig.ready() on 2026-05-20).

from django.db import migrations


def create_missing_profiles(apps, schema_editor):
    User = apps.get_model("auth", "User")
    Profile = apps.get_model("core", "Profile")

    profiles = [
        Profile(user=user) for user in User.objects.filter(profile__isnull=True)
    ]

    Profile.objects.bulk_create(profiles, ignore_conflicts=True)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_schema_search_vector'),
    ]

    operations = [
        # Reversing is a no-op: backfilled Profiles can't be told apart from
        # ones created by the signal, and may already have API keys or orgs.
        migrations.RunPython(create_missing_profiles, migrations.RunPython.noop),
    ]
