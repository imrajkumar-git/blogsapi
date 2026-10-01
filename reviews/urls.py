from django.urls import path

from .views import MyReviewView, ReviewDestroyView, ReviewListCreateView

urlpatterns = [
    path("", ReviewListCreateView.as_view(), name="review-list"),
    path("mine/", MyReviewView.as_view(), name="review-mine"),
    path("<int:pk>/", ReviewDestroyView.as_view(), name="review-detail"),
]
