from django.db import migrations


def add_flag(apps, schema_editor):
    FeatureFlag = apps.get_model("flags", "FeatureFlag")
    FeatureFlag.objects.update_or_create(
        key="webhooks_enabled",
        defaults={
            "description": "Enable outgoing webhooks for this tenant",
            "enabled_by_default": False,
        },
    )


def remove_flag(apps, schema_editor):
    FeatureFlag = apps.get_model("flags", "FeatureFlag")
    FeatureFlag.objects.filter(key="webhooks_enabled").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("flags", "0003_lead_sla_flag"),  # change to your latest flags migration
    ]
    operations = [migrations.RunPython(add_flag, remove_flag)]
