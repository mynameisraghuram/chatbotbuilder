from core.audit.models import AuditLog


def audit(tenant_id, action, entity_type, entity_id, actor_user_id=None, data=None):
    AuditLog.objects.create(
        tenant_id=tenant_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
        data_json=data or {},
    )
