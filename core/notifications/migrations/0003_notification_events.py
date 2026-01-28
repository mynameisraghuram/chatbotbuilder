from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0002_rename_notif_pref_tenant_user_idx_notificatio_tenant__52fe84_idx_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationEvent",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("tenant_id", models.UUIDField(db_index=True)),
                ("user_id", models.UUIDField(db_index=True)),
                ("type", models.CharField(max_length=100, db_index=True)),
                ("payload_json", models.JSONField(default=dict, blank=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ("digested_at", models.DateTimeField(null=True, blank=True, db_index=True)),
            ],
            options={"db_table": "notification_events"},
        ),
        migrations.AddIndex(
            model_name="notificationevent",
            index=models.Index(
                fields=["tenant_id", "user_id", "digested_at", "created_at"],
                name="notif_evt_tu_digest_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="notificationevent",
            index=models.Index(
                fields=["tenant_id", "type", "created_at"],
                name="notif_evt_ttype_created_idx",
            ),
        ),
    ]
