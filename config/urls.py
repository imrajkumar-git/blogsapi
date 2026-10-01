from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    # These three prefixes match NEXT_PUBLIC_API_URL / _BLOG_API_URL / _REVIEWS_API_URL
    # in frontend/.env.local.example.
    path("api/auth/", include("accounts.urls")),
    path("api/blog/", include("blog.urls")),
    path("api/reviews/", include("reviews.urls")),
]

# Uploaded avatars and cover images. In production, serve MEDIA_ROOT from your
# web server / object storage instead (see README).
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
