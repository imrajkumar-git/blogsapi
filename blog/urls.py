from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import CommentDestroyView, PostViewSet

router = SimpleRouter()
router.register(r"posts", PostViewSet, basename="post")

urlpatterns = [
    path("comments/<int:pk>/", CommentDestroyView.as_view(), name="comment-detail"),
    path("", include(router.urls)),
]
