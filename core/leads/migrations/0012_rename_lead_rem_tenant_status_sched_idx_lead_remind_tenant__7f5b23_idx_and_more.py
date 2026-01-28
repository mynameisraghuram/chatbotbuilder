from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0011_lead_reminder_delivery_fields"),
    ]

    operations = [
        # NO-OP migration
        # Index rename operations removed because indexes do not exist
        # Field removals already applied earlier in the chain
    ]
