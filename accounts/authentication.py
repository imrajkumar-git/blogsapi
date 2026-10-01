from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication


class VerifiedJWTAuthentication(JWTAuthentication):
    """JWT auth that also requires admin approval (is_verified).

    Without this, a token issued before an admin un-verified someone would
    keep working until it expired.
    """

    def get_user(self, validated_token):
        user = super().get_user(validated_token)  # already rejects inactive users
        if not user.is_verified:
            raise AuthenticationFailed(
                "Your account is pending admin verification.", code="user_not_verified"
            )
        return user
