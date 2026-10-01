from django.db.models import BooleanField, Count, Exists, OuterRef, Prefetch, Q, Value
from rest_framework import generics, status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from common.permissions import IsOwnerOrStaff

from .models import Comment, Like, Post
from .serializers import CommentSerializer, PostDetailSerializer, PostListSerializer


def visible_posts(user):
    """Published posts for everyone; drafts only for their author and staff."""
    qs = Post.objects.select_related("author")
    if user.is_authenticated:
        if user.is_staff:
            return qs
        return qs.filter(Q(is_published=True) | Q(author=user))
    return qs.filter(is_published=True)


class PostViewSet(viewsets.ModelViewSet):
    """/api/blog/posts/ — looked up by slug."""

    lookup_field = "slug"
    permission_classes = [IsAuthenticatedOrReadOnly, IsOwnerOrStaff]

    def get_serializer_class(self):
        return PostListSerializer if self.action == "list" else PostDetailSerializer

    def get_queryset(self):
        user = self.request.user
        qs = visible_posts(user).annotate(
            likes_count=Count("likes", distinct=True),
            comments_count=Count("comments", distinct=True),
        )
        # Explicit: Meta.ordering is ignored on queries that use GROUP BY.
        qs = qs.order_by("-created_at", "-id")
        if user.is_authenticated:
            qs = qs.annotate(
                liked_by_me=Exists(Like.objects.filter(post=OuterRef("pk"), user=user))
            )
        else:
            qs = qs.annotate(liked_by_me=Value(False, output_field=BooleanField()))
        if self.action != "list":
            qs = qs.prefetch_related(
                Prefetch("comments", Comment.objects.select_related("user"))
            )
        return qs

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def like(self, request, slug=None):
        """Toggle the current user's like."""
        post = self.get_object()
        _, created = Like.objects.get_or_create(post=post, user=request.user)
        if not created:
            Like.objects.filter(post=post, user=request.user).delete()
        return Response({"liked_by_me": created, "likes_count": post.likes.count()})

    @action(
        detail=True,
        methods=["get", "post"],
        url_path="comments",
        permission_classes=[IsAuthenticatedOrReadOnly],
    )
    def comments(self, request, slug=None):
        post = self.get_object()
        if request.method == "GET":
            comments = post.comments.select_related("user")
            return Response(CommentSerializer(comments, many=True, context={"request": request}).data)
        serializer = CommentSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save(post=post, user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CommentDestroyView(generics.DestroyAPIView):
    """DELETE /api/blog/comments/<id>/ — comment author or staff."""

    queryset = Comment.objects.select_related("user", "post")
    permission_classes = [IsAuthenticated, IsOwnerOrStaff]
