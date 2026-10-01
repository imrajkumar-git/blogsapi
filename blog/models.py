import uuid

from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils.text import slugify

from common.categories import BLOG_CATEGORIES
from common.files import delete_file_after_commit


class Post(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts"
    )
    title = models.CharField(max_length=200)
    # Generated once from the title and never changed, so URLs stay stable.
    slug = models.SlugField(max_length=80, unique=True, allow_unicode=True, editable=False)
    excerpt = models.CharField(max_length=300, blank=True)
    content = models.TextField()
    category = models.CharField(max_length=20, choices=BLOG_CATEGORIES, blank=True)
    cover_image = models.FileField(upload_to="blog/covers/%Y/%m/", blank=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.title

    def _make_slug(self):
        base = slugify(self.title, allow_unicode=True)[:60].strip("-") or "post"
        candidate = base
        while Post.objects.filter(slug=candidate).exists():
            candidate = f"{base}-{uuid.uuid4().hex[:6]}"
        return candidate

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._make_slug()
        super().save(*args, **kwargs)


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blog_comments"
    )
    content = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.user} on {self.post}"


class Like(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="post_likes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["post", "user"], name="blog_like_unique_per_user")
        ]


@receiver(post_delete, sender=Post)
def _delete_cover(sender, instance, **kwargs):
    delete_file_after_commit(instance.cover_image)
