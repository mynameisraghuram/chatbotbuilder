from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0008_rename_lead_events_tenant_lead_created_idx_lead_events_tenant__efb09a_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="assigned_to_user_id",
            field=models.UUIDField(null=True, blank=True, db_index=True),
        ),
    ]
