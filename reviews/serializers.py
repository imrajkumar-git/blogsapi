from rest_framework import serializers

from accounts.serializers import PublicUserSerializer

from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    user = PublicUserSerializer(read_only=True)
    rating = serializers.IntegerField(min_value=1, max_value=5)
    content = serializers.CharField(max_length=1000)

    class Meta:
        model = Review
        fields = ("id", "user", "rating", "content", "created_at", "updated_at")
        read_only_fields = ("id", "user", "created_at", "updated_at")
