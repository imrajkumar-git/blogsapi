import base64
import shutil
import tempfile

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from accounts.models import User

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def png(name="pic.png"):
    return SimpleUploadedFile(name, PNG_BYTES, content_type="image/png")


class BaseAPITestCase(APITestCase):
    """Isolated MEDIA_ROOT, cleared throttle cache, and user helpers."""

    def setUp(self):
        super().setUp()
        cache.clear()
        self._media = tempfile.mkdtemp()
        self._override = override_settings(MEDIA_ROOT=self._media)
        self._override.enable()
        self.addCleanup(self._override.disable)
        self.addCleanup(shutil.rmtree, self._media, ignore_errors=True)

    def make_user(self, username="alice", verified=True, **extra):
        extra.setdefault("is_verified", verified)
        return User.objects.create_user(
            email=f"{username}@example.com", username=username, password="Str0ng-pass!word", **extra
        )

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client
