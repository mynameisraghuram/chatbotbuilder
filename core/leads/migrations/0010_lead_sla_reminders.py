from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0009_lead_assignment"),
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="last_contacted_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="lead",
            name="next_action_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.CreateModel(
            name="LeadSlaPolicy",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("is_enabled", models.BooleanField(default=True)),
                ("minutes_by_status", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(db_index=True, default=timezone.now)),
                ("updated_at", models.DateTimeField(db_index=True, default=timezone.now)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lead_sla_policies", to="tenants.tenant")),
            ],
            options={"db_table": "lead_sla_policies"},
        ),
        migrations.CreateModel(
            name="LeadReminder",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("reason", models.CharField(default="sla", max_length=64)),
                ("status", models.CharField(choices=[("scheduled", "Scheduled"), ("sent", "Sent"), ("canceled", "Canceled"), ("failed", "Failed")], db_index=True, default="scheduled", max_length=16)),
                ("scheduled_for", models.DateTimeField(db_index=True)),
                ("sent_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("last_error", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(db_index=True, default=timezone.now)),
                ("updated_at", models.DateTimeField(db_index=True, default=timezone.now)),
                ("lead", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reminders", to="leads.lead")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lead_reminders", to="tenants.tenant")),
            ],
            options={"db_table": "lead_reminders"},
        ),
        migrations.AddIndex(
            model_name="leadslapolicy",
            index=models.Index(fields=["tenant", "is_enabled"], name="lead_sla_tenant_enabled_idx"),
        ),
        migrations.AddIndex(
            model_name="leadreminder",
            index=models.Index(fields=["tenant", "status", "scheduled_for"], name="lead_rem_tenant_status_sched_idx"),
        ),
        migrations.AddIndex(
            model_name="leadreminder",
            index=models.Index(fields=["tenant", "lead", "created_at"], name="lead_rem_tenant_lead_created_idx"),
        ),
        migrations.AddConstraint(
            model_name="leadreminder",
            constraint=models.UniqueConstraint(fields=("tenant", "lead", "reason", "scheduled_for"), name="uniq_lead_reminder_per_time"),
        ),
    ]
