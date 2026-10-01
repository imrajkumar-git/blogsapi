from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower
from django.db.models.signals import post_delete
from django.dispatch import receiver

from common.files import delete_file_after_commit


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, username, password, **extra):
        if not email:
            raise ValueError("Users must have an email address.")
        if not username:
            raise ValueError("Users must have a username.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, username=username, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, username, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, username, password, **extra)

    def create_superuser(self, email, username, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_verified", True)  # admins must be able to log in
        return self._create_user(email, username, password, **extra)


class User(AbstractUser):
    """Log in with email; `username` is the public display handle.

    New accounts start with is_verified=False and cannot log in until an admin
    approves them (Admin Panel → Users, or Django admin).
    """

    email = models.EmailField(unique=True)
    is_verified = models.BooleanField(default=False)

    phone_number = models.CharField(max_length=32, blank=True)
    bio = models.CharField(max_length=500, blank=True)
    profile_picture = models.FileField(upload_to="avatars/%Y/%m/", blank=True)

    website_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)

    # Category ids the user picked at signup (see common/categories.py).
    preferred_categories = models.JSONField(default=list, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        constraints = [
            # "Alice" and "alice" must not coexist — the frontend identifies
            # authors by username.
            models.UniqueConstraint(Lower("username"), name="accounts_user_username_ci_unique"),
        ]

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email


@receiver(post_delete, sender=User)
def _delete_avatar(sender, instance, **kwargs):
    delete_file_after_commit(instance.profile_picture)
