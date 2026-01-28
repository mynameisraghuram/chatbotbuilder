from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("conversations", "0001_initial"),
        ("leads", "0001_initial"),  # assumes leads app migrations start at 0001
    ]

    operations = [
        migrations.AddField(
            model_name="conversation",
            name="lead",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="conversations",
                to="leads.lead",
            ),
        ),
    ]
