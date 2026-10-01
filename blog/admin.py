from django.contrib import admin

from .models import Comment, Like, Post


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    raw_id_fields = ("user",)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "category", "is_published", "created_at")
    list_filter = ("is_published", "category")
    search_fields = ("title", "author__username", "author__email")
    raw_id_fields = ("author",)
    readonly_fields = ("slug",)
    inlines = [CommentInline]


admin.site.register(Like)
