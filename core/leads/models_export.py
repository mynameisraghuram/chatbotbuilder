from django.db import models
from django.utils import timezone

class LeadExport(models.Model):
    id = models.BigAutoField(primary_key=True)
    tenant_id = models.UUIDField(db_index=True)
    requested_by_user_id = models.UUIDField(db_index=True)

    status = models.CharField(
        max_length=16,
        choices=[
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("done", "Done"),
            ("failed", "Failed"),
        ],
        default="pending",
        db_index=True,
    )

    file_url = models.TextField(blank=True)
    error = models.TextField(blank=True)

    created_at = models.DateTimeField(default=timezone.now)
