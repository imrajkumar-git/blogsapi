from django.http import JsonResponse
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsOwnerOrStaff

from .models import Review
from .serializers import ReviewSerializer


class ReviewListCreateView(generics.ListCreateAPIView):
    """GET /api/reviews/ is public. POST creates the caller's review, or
    updates it if they already have one (the frontend re-POSTs to edit)."""

    queryset = Review.objects.select_related("user")
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def create(self, request, *args, **kwargs):
        existing = Review.objects.filter(user=request.user).first()
        serializer = self.get_serializer(existing, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        code = status.HTTP_200_OK if existing else status.HTTP_201_CREATED
        return Response(serializer.data, status=code)


class MyReviewView(APIView):
    """GET /api/reviews/mine/ — the caller's review, or JSON `null`.

    Always 200: the frontend treats any error here as "could not load reviews".
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        review = Review.objects.select_related("user").filter(user=request.user).first()
        if review is None:
            return JsonResponse(None, safe=False)
        return Response(ReviewSerializer(review, context={"request": request}).data)


class ReviewDestroyView(generics.DestroyAPIView):
    """DELETE /api/reviews/<id>/ — the review's author or staff."""

    queryset = Review.objects.select_related("user")
    permission_classes = [IsAuthenticated, IsOwnerOrStaff]
