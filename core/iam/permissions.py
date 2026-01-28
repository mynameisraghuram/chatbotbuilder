from rest_framework.permissions import BasePermission
from core.iam.models import TenantMembership


class IsTenantMember(BasePermission):
    """
    Requires:
      - request.tenant_id (set by TenantScopeMiddleware)
      - authenticated user
    Attaches:
      - request.tenant_role
    """

    def has_permission(self, request, view):
        tenant_id = getattr(request, "tenant_id", None)
        if not tenant_id:
            return False

        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False

        membership = (
            TenantMembership.objects.filter(tenant_id=tenant_id, user_id=user.id)
            .only("role")
            .first()
        )
        if not membership:
            return False

        request.tenant_role = membership.role
        return True


class HasRole(BasePermission):
    """
    Usage:
      permission_classes = [IsAuthenticated, IsTenantMember, HasRole.with_roles("owner","admin")]
    """

    allowed_roles: tuple[str, ...] = tuple()

    @classmethod
    def with_roles(cls, *roles: str):
        return type("HasRoleSub", (cls,), {"allowed_roles": roles})

    def has_permission(self, request, view):
        role = getattr(request, "tenant_role", None)
        return role in self.allowed_roles
