from rest_framework.permissions import BasePermission, SAFE_METHODS
from .models import WorkspaceMember


class IsWorkspaceMemberOrReadOnly(BasePermission):
    """Example object-level policy: membership is required for workspace data."""
    def has_object_permission(self, request, view, obj):
        workspace = getattr(obj, "workspace", obj)
        if request.method in SAFE_METHODS:
            return WorkspaceMember.objects.filter(workspace=workspace, user=request.user).exists()
        return WorkspaceMember.objects.filter(
            workspace=workspace, user=request.user,
            role__in=[WorkspaceMember.Role.ADMIN, WorkspaceMember.Role.EDITOR]
        ).exists()
