from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
    ("leads", "0004_rename_otp_tenant_lead_created_idx_otp_verific_tenant__cbbaf0_idx_and_more"),
    ]


    operations = [
        migrations.AlterField(
            model_name="lead",
            name="chatbot",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="leads",
                to="chatbots.chatbot",
            ),
        ),
    ]
