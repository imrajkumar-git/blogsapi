from django.urls import include, path
from rest_framework.routers import SimpleRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import AdminUserViewSet, LoginView, ProfileView, RegisterView

router = SimpleRouter()
router.register(r"admin/users", AdminUserViewSet, basename="admin-user")

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("", include(router.urls)),
]
