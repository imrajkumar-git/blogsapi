from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsOwnerOrStaff(BasePermission):
    """Anyone may read; only the owner (author/user) or staff may change."""

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        if not (user and user.is_authenticated):
            return False
        owner_id = getattr(obj, "author_id", getattr(obj, "user_id", None))
        return user.is_staff or owner_id == user.id
