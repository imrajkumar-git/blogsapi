from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from rest_framework import generics, mixins, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, BasePermission, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import (
    AdminUserSerializer,
    LoginSerializer,
    RegisterSerializer,
    UserSerializer,
)

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register/ — creates an *unverified* account."""

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    # Ignore any stale Authorization header the frontend may attach.
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        data = UserSerializer(user, context={"request": request}).data
        return Response(data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """POST /api/auth/login/ {email, password} -> {access, refresh, user}."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        update_last_login(None, user)
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user, context={"request": request}).data,
            }
        )


class ProfileView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/auth/profile/ — the signed-in user's own data."""

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class CanManageTarget(BasePermission):
    """Only superusers may modify or delete superuser accounts."""

    def has_object_permission(self, request, view, obj):
        return request.user.is_superuser or not obj.is_superuser


class AdminUserViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """/api/auth/admin/users/ — staff-only user management."""

    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminUser, CanManageTarget]
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        # Unverified accounts first so pending approvals are easy to find.
        return User.objects.order_by("is_verified", "-date_joined")

    def perform_destroy(self, instance):
        if instance.pk == self.request.user.pk:
            raise PermissionDenied("You can't delete your own account.")
        instance.delete()
