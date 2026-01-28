from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0005_alter_lead_chatbot_nullable"),
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="LeadEvent",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("actor_user_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("type", models.CharField(db_index=True, max_length=64)),
                ("source", models.CharField(choices=[("system", "System"), ("public", "Public"), ("dashboard", "Dashboard")], default="system", max_length=16)),
                ("data_json", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(db_index=True, default=timezone.now)),
                ("lead", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="leads.lead")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lead_events", to="tenants.tenant")),
            ],
            options={"db_table": "lead_events"},
        ),
        migrations.AddIndex(
            model_name="leadevent",
            index=models.Index(fields=["tenant", "lead", "created_at"], name="lead_events_tenant_lead_created_idx"),
        ),
        migrations.AddIndex(
            model_name="leadevent",
            index=models.Index(fields=["tenant", "type", "created_at"], name="lead_events_tenant_type_created_idx"),
        ),
    ]
