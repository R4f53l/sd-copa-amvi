"""
Superusers created before ``User.save()`` started enforcing it kept the
default "table official" role. Make them administrators.
"""

from django.db import migrations


def superusers_to_admin(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(is_superuser=True).update(role="ADMIN", is_staff=True)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        # Nothing to undo: the previous role was just the default.
        migrations.RunPython(superusers_to_admin, migrations.RunPython.noop),
    ]
