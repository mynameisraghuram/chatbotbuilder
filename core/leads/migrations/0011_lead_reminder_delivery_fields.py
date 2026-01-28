from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0010_lead_sla_reminders"),
    ]

    operations = [
        migrations.AddField(
            model_name="leadreminder",
            name="next_attempt_at",
            field=models.DateTimeField(null=True, blank=True, db_index=True),
        ),
        migrations.AddField(
            model_name="leadreminder",
            name="last_channel",
            field=models.CharField(max_length=20, null=True, blank=True),
        ),
    ]
