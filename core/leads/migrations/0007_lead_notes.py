from django.db import migrations, models
import django.db.models.deletion
import uuid
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0006_lead_events"),
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="LeadNote",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("body", models.TextField()),
                ("created_by_user_id", models.UUIDField(db_index=True)),
                ("updated_by_user_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(db_index=True, default=timezone.now)),
                ("updated_at", models.DateTimeField(db_index=True, default=timezone.now)),
                ("deleted_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("lead", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notes", to="leads.lead")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lead_notes", to="tenants.tenant")),
            ],
            options={"db_table": "lead_notes"},
        ),
        migrations.AddIndex(
            model_name="leadnote",
            index=models.Index(fields=["tenant", "lead", "created_at"], name="lead_notes_tenant_lead_created_idx"),
        ),
        migrations.AddIndex(
            model_name="leadnote",
            index=models.Index(fields=["tenant", "lead", "deleted_at"], name="lead_notes_tenant_lead_deleted_idx"),
        ),
    ]
