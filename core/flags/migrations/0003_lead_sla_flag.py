from django.db import migrations


def add_flag(apps, schema_editor):
    FeatureFlag = apps.get_model("flags", "FeatureFlag")
    FeatureFlag.objects.update_or_create(
        key="lead_sla_enabled",
        defaults={
            "description": "Enable lead SLA reminders and scheduling",
            "enabled_by_default": False,
        },
    )


def remove_flag(apps, schema_editor):
    FeatureFlag = apps.get_model("flags", "FeatureFlag")
    FeatureFlag.objects.filter(key="lead_sla_enabled").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("flags", "0002_lead_enrichment_flag"),
    ]

    operations = [
        migrations.RunPython(add_flag, remove_flag),
    ]
