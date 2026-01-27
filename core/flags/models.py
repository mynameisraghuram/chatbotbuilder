import uuid
from django.db import models
from core.tenants.models import Tenant

class FeatureFlag(models.Model):
    """
    Global flag catalog. Immutable-ish (change carefully).
    """
    key = models.CharField(max_length=128, primary_key=True)
    description = models.CharField(max_length=255, blank=True, default="")
    enabled_by_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.key

class TenantFeatureFlag(models.Model):
    """
    Per-tenant override. Tenant isolation enforced by FK.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="feature_flags")
    key = models.ForeignKey(FeatureFlag, to_field="key", db_column="key", on_delete=models.CASCADE)
    is_enabled = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "key"], name="uq_tenant_flag"),
        ]
        indexes = [
            models.Index(fields=["tenant"]),
        ]
