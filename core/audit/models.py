from django.db import models
from django.utils import timezone

class AuditLog(models.Model):
    id = models.BigAutoField(primary_key=True)

    tenant_id = models.UUIDField(db_index=True)
    actor_user_id = models.UUIDField(null=True, blank=True)

    action = models.CharField(max_length=64, db_index=True)
    entity_type = models.CharField(max_length=64)
    entity_id = models.UUIDField()

    data_json = models.JSONField(default=dict)

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
