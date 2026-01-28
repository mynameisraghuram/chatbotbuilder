from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0002_rename_leads_tenant_created_at_idx_leads_tenant__34bb46_idx_and_more"),
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="OtpVerification",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("email", models.EmailField(db_index=True, max_length=254)),
                ("otp_hash", models.CharField(max_length=64)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("attempt_count", models.PositiveIntegerField(default=0)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(default=timezone.now, db_index=True)),
                ("lead", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="otp_verifications", to="leads.lead")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="otp_verifications", to="tenants.tenant")),
            ],
            options={"db_table": "otp_verifications"},
        ),
        migrations.AddIndex(
            model_name="otpverification",
            index=models.Index(fields=["tenant", "lead", "created_at"], name="otp_tenant_lead_created_idx"),
        ),
        migrations.AddIndex(
            model_name="otpverification",
            index=models.Index(fields=["tenant", "email", "expires_at"], name="otp_tenant_email_expires_idx"),
        ),
    ]
