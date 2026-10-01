from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import RegexValidator, URLValidator
from django.conf import settings
from rest_framework import serializers
from rest_framework.exceptions import APIException

from common.categories import CATEGORY_IDS
from common.files import delete_stored_file_after_commit
from common.uploads import clean_image_upload

User = get_user_model()

SOCIAL_FIELDS = ("website_url", "twitter_url", "instagram_url", "linkedin_url", "github_url")


class LenientURLField(serializers.CharField):
    """http(s) URL; adds https:// if the user typed 'github.com/me'."""

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("allow_blank", True)
        kwargs.setdefault("max_length", 200)
        super().__init__(**kwargs)
        self.validators.append(URLValidator(schemes=["http", "https"]))

    def run_validation(self, data=serializers.empty):
        if isinstance(data, str):
            data = data.strip()
            if data and "://" not in data:
                data = "https://" + data
        return super().run_validation(data)


class UsernameUniquenessMixin:
    def validate_username(self, value):
        qs = User.objects.filter(username__iexact=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return value


class PublicUserSerializer(serializers.ModelSerializer):
    """Minimal author/commenter info — never includes email."""

    class Meta:
        model = User
        fields = ("id", "username", "profile_picture")
        read_only_fields = fields


class UserSerializer(UsernameUniquenessMixin, serializers.ModelSerializer):
    """The signed-in user's own profile (login response, /profile/)."""

    website_url = LenientURLField()
    twitter_url = LenientURLField()
    instagram_url = LenientURLField()
    linkedin_url = LenientURLField()
    github_url = LenientURLField()
    profile_picture = serializers.FileField(required=False)
    preferred_categories = serializers.ListField(
        child=serializers.ChoiceField(choices=CATEGORY_IDS), required=False
    )
    phone_number = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=32,
        validators=[RegexValidator(r"^[0-9+()\-.\s]*$", "Enter a valid phone number.")],
    )

    class Meta:
        model = User
        fields = (
            "id", "username", "email", "first_name", "last_name", "phone_number", "bio",
            "profile_picture", *SOCIAL_FIELDS, "preferred_categories",
            "is_verified", "is_staff", "is_active", "date_joined",
        )
        read_only_fields = ("id", "email", "is_verified", "is_staff", "is_active", "date_joined")

    def validate_profile_picture(self, value):
        return clean_image_upload(value, settings.AVATAR_MAX_BYTES)

    def update(self, instance, validated_data):
        old_name = instance.profile_picture.name
        storage = instance.profile_picture.storage
        instance = super().update(instance, validated_data)
        if old_name and instance.profile_picture.name != old_name:
            delete_stored_file_after_commit(storage, old_name)
        return instance


class RegisterSerializer(UsernameUniquenessMixin, serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password2 = serializers.CharField(write_only=True, trim_whitespace=False)
    preferred_categories = serializers.ListField(
        child=serializers.ChoiceField(choices=CATEGORY_IDS), required=False
    )
    phone_number = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=32,
        validators=[RegexValidator(r"^[0-9+()\-.\s]*$", "Enter a valid phone number.")],
    )

    class Meta:
        model = User
        fields = (
            "username", "email", "password", "password2", "first_name", "last_name",
            "phone_number", "bio", "preferred_categories",
        )

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with that email already exists.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password2": ["Passwords don't match."]})
        candidate = User(
            username=attrs.get("username", ""),
            email=attrs.get("email", ""),
            first_name=attrs.get("first_name", ""),
            last_name=attrs.get("last_name", ""),
        )
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)


class InvalidCredentials(APIException):
    # 400, not 401: the frontend's axios interceptor treats 401 as "token expired".
    status_code = 400
    default_detail = "Invalid email or password."
    default_code = "invalid_credentials"


class AccountNotAllowed(APIException):
    status_code = 403
    default_code = "account_not_allowed"


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        email = attrs["email"].strip().lower()
        user = User.objects.filter(email=email).first()
        if user is None:
            User().set_password(attrs["password"])  # equalise timing, no user enumeration
            raise InvalidCredentials()
        if not user.check_password(attrs["password"]):
            raise InvalidCredentials()
        # Only reveal account state once the password is proven correct.
        if not user.is_active:
            raise AccountNotAllowed("This account has been disabled. Please contact the site owner.")
        if not user.is_verified:
            raise AccountNotAllowed("Your account is pending admin verification.")
        attrs["user"] = user
        return attrs


class AdminUserSerializer(UsernameUniquenessMixin, serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id", "username", "email", "first_name", "last_name", "phone_number",
            "profile_picture", "is_staff", "is_active", "is_verified", "date_joined",
        )
        read_only_fields = ("id", "email", "phone_number", "profile_picture", "date_joined")

    def validate(self, attrs):
        request = self.context["request"]
        if self.instance is not None and self.instance.pk == request.user.pk:
            for flag in ("is_staff", "is_active", "is_verified"):
                if attrs.get(flag) is False:
                    raise serializers.ValidationError(
                        {flag: "You can't remove this from your own account."}
                    )
        return attrs
