from django.conf import settings
from rest_framework import serializers

from accounts.serializers import PublicUserSerializer
from common.categories import BLOG_CATEGORIES
from common.files import delete_stored_file_after_commit
from common.uploads import clean_image_upload

from .models import Comment, Post


class CommentSerializer(serializers.ModelSerializer):
    user = PublicUserSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ("id", "user", "content", "created_at")
        read_only_fields = ("id", "user", "created_at")
        extra_kwargs = {"content": {"max_length": 2000}}


class PostListSerializer(serializers.ModelSerializer):
    """Card-sized representation (no body, no comments)."""

    author = PublicUserSerializer(read_only=True)
    cover = serializers.FileField(source="cover_image", read_only=True)
    likes_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    liked_by_me = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = (
            "id", "slug", "title", "excerpt", "category", "cover", "is_published",
            "author", "created_at", "updated_at", "likes_count", "comments_count",
            "liked_by_me",
        )
        read_only_fields = fields

    # Counts are annotated by the view's queryset; fall back to queries for
    # instances that were just created/updated and so lack the annotations.
    def get_likes_count(self, obj):
        value = getattr(obj, "likes_count", None)
        return value if value is not None else obj.likes.count()

    def get_comments_count(self, obj):
        value = getattr(obj, "comments_count", None)
        return value if value is not None else obj.comments.count()

    def get_liked_by_me(self, obj):
        value = getattr(obj, "liked_by_me", None)
        if value is not None:
            return bool(value)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and obj.likes.filter(user=user).exists())


class PostDetailSerializer(PostListSerializer):
    """Full post: body + comments, and the writable fields."""

    comments = CommentSerializer(many=True, read_only=True)
    category = serializers.ChoiceField(choices=BLOG_CATEGORIES, required=False, allow_blank=True)
    # Upload field is `cover_image`; the stored file is read back as `cover`.
    cover_image = serializers.FileField(write_only=True, required=False)
    remove_cover_image = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta(PostListSerializer.Meta):
        fields = PostListSerializer.Meta.fields + (
            "content", "comments", "cover_image", "remove_cover_image",
        )
        read_only_fields = ("id", "slug", "author", "created_at", "updated_at")

    def validate_cover_image(self, value):
        return clean_image_upload(value, settings.BLOG_COVER_MAX_BYTES)

    def create(self, validated_data):
        validated_data.pop("remove_cover_image", None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        remove = validated_data.pop("remove_cover_image", False)
        if remove and "cover_image" not in validated_data:
            validated_data["cover_image"] = ""
        old_name = instance.cover_image.name
        storage = instance.cover_image.storage
        instance = super().update(instance, validated_data)
        if old_name and instance.cover_image.name != old_name:
            delete_stored_file_after_commit(storage, old_name)
        return instance
