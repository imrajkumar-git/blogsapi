from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import User


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email", "username")


class CustomUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm
    ordering = ("is_verified", "-date_joined")
    list_display = ("email", "username", "is_verified", "is_staff", "is_active", "date_joined")
    list_filter = ("is_verified", "is_staff", "is_active")
    search_fields = ("email", "username", "first_name", "last_name")
    actions = ["verify_users"]

    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            "Community profile",
            {
                "fields": (
                    "is_verified", "phone_number", "bio", "profile_picture",
                    "website_url", "twitter_url", "instagram_url", "linkedin_url",
                    "github_url", "preferred_categories",
                )
            },
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "username", "password1", "password2", "is_verified"),
            },
        ),
    )

    @admin.action(description="Verify selected users (let them log in)")
    def verify_users(self, request, queryset):
        updated = queryset.update(is_verified=True)
        self.message_user(request, f"{updated} user(s) verified.", messages.SUCCESS)
