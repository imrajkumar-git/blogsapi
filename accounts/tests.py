import os

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from common.testing import BaseAPITestCase, png

from .models import User

REGISTER = "/api/auth/register/"
LOGIN = "/api/auth/login/"
PASSWORD = "Str0ng-pass!word"


def register_payload(**over):
    data = {
        "username": "newbie", "email": "Newbie@Example.com", "password": PASSWORD,
        "password2": PASSWORD, "first_name": "New", "last_name": "Bie",
        "phone_number": "+971 50 123 4567", "bio": "hi", "preferred_categories": ["travel", "food"],
    }
    data.update(over)
    return data


class RegisterTests(BaseAPITestCase):
    def test_register_creates_unverified_account(self):
        r = self.client.post(REGISTER, register_payload(), format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertNotIn("password", r.data)
        user = User.objects.get(username="newbie")
        self.assertEqual(user.email, "newbie@example.com")
        self.assertFalse(user.is_verified)
        self.assertFalse(user.is_staff)
        self.assertEqual(user.preferred_categories, ["travel", "food"])

    def test_password_mismatch(self):
        r = self.client.post(REGISTER, register_payload(password2="nope-nope-123"), format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("password2", r.data)

    def test_weak_password_rejected(self):
        r = self.client.post(
            REGISTER, register_payload(password="12345678", password2="12345678"), format="json"
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("password", r.data)

    def test_duplicate_email_and_username_are_case_insensitive(self):
        self.make_user("taken")
        r = self.client.post(REGISTER, register_payload(email="TAKEN@example.com"), format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("email", r.data)
        r = self.client.post(REGISTER, register_payload(username="TAKEN"), format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("username", r.data)

    def test_unknown_category_rejected(self):
        r = self.client.post(REGISTER, register_payload(preferred_categories=["bogus"]), format="json")
        self.assertEqual(r.status_code, 400)

    def test_cannot_self_assign_staff(self):
        r = self.client.post(REGISTER, register_payload(is_staff=True, is_verified=True), format="json")
        self.assertEqual(r.status_code, 201)
        user = User.objects.get(username="newbie")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_verified)

    def test_stale_token_header_does_not_break_register(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
        self.assertEqual(client.post(REGISTER, register_payload(), format="json").status_code, 201)


class LoginTests(BaseAPITestCase):
    def test_login_returns_tokens_and_user(self):
        user = self.make_user("alice")
        r = self.client.post(LOGIN, {"email": "ALICE@example.com", "password": PASSWORD}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data["access"] and r.data["refresh"])
        self.assertEqual(r.data["user"]["username"], "alice")
        self.assertEqual(r.data["user"]["id"], user.id)
        self.assertNotIn("password", r.data["user"])

    def test_access_token_works_and_refresh_issues_new_access(self):
        self.make_user("alice")
        tokens = self.client.post(LOGIN, {"email": "alice@example.com", "password": PASSWORD}, format="json").data
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(client.get("/api/auth/profile/").status_code, 200)
        r = self.client.post("/api/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("access", r.data)

    def test_wrong_password_is_400_and_not_reported_as_pending(self):
        self.make_user("alice")
        r = self.client.post(LOGIN, {"email": "alice@example.com", "password": "wrong"}, format="json")
        self.assertEqual(r.status_code, 400)  # never 401: that would trigger token refresh
        self.assertNotIn("pending", str(r.data).lower())

    def test_unknown_email_looks_the_same_as_wrong_password(self):
        r = self.client.post(LOGIN, {"email": "ghost@example.com", "password": "x"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(str(r.data["detail"]), "Invalid email or password.")

    def test_unverified_account_gets_pending_message(self):
        self.make_user("alice", verified=False)
        r = self.client.post(LOGIN, {"email": "alice@example.com", "password": PASSWORD}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertIn("pending", str(r.data["detail"]).lower())  # what the frontend looks for

    def test_unverified_status_not_revealed_with_wrong_password(self):
        self.make_user("alice", verified=False)
        r = self.client.post(LOGIN, {"email": "alice@example.com", "password": "wrong"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_disabled_account_message_is_not_mistaken_for_pending(self):
        self.make_user("alice", is_active=False)
        r = self.client.post(LOGIN, {"email": "alice@example.com", "password": PASSWORD}, format="json")
        self.assertEqual(r.status_code, 403)
        text = str(r.data).lower()
        for needle in ("pending", "not verified", "inactive", "awaiting"):
            self.assertNotIn(needle, text)

    def test_stale_token_header_does_not_break_login(self):
        self.make_user("alice")
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer expired.or.garbage")
        r = client.post(LOGIN, {"email": "alice@example.com", "password": PASSWORD}, format="json")
        self.assertEqual(r.status_code, 200)

    def test_login_is_throttled(self):
        for _ in range(10):
            self.client.post(LOGIN, {"email": "x@example.com", "password": "x"}, format="json")
        r = self.client.post(LOGIN, {"email": "x@example.com", "password": "x"}, format="json")
        self.assertEqual(r.status_code, 429)

    def test_token_stops_working_when_admin_unverifies_user(self):
        user = self.make_user("alice")
        tokens = self.client.post(LOGIN, {"email": "alice@example.com", "password": PASSWORD}, format="json").data
        user.is_verified = False
        user.save()
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(client.get("/api/auth/profile/").status_code, 401)

    def test_superuser_created_by_manage_py_can_log_in(self):
        User.objects.create_superuser("root@example.com", "root", PASSWORD)
        r = self.client.post(LOGIN, {"email": "root@example.com", "password": PASSWORD}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["user"]["is_staff"])


class ProfileTests(BaseAPITestCase):
    def test_requires_auth(self):
        self.assertEqual(self.client.get("/api/auth/profile/").status_code, 401)

    def test_get_profile_shape(self):
        r = self.client_for(self.make_user("alice")).get("/api/auth/profile/")
        for key in ("id", "username", "email", "first_name", "last_name", "bio", "profile_picture",
                    "website_url", "github_url", "is_verified", "is_staff", "date_joined"):
            self.assertIn(key, r.data)

    def test_multipart_patch_like_the_dashboard_form(self):
        user = self.make_user("alice")
        client = self.client_for(user)
        r = client.patch("/api/auth/profile/", {
            "username": "alice2", "first_name": "A", "last_name": "L", "bio": "hello",
            "website_url": "", "twitter_url": "x.com/alice", "instagram_url": "", "linkedin_url": "",
            "github_url": "https://github.com/alice", "profile_picture": png(),
        }, format="multipart")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["username"], "alice2")
        self.assertEqual(r.data["twitter_url"], "https://x.com/alice")
        self.assertTrue(r.data["profile_picture"].startswith("http://testserver/media/avatars/"))
        user.refresh_from_db()
        self.assertTrue(os.path.exists(user.profile_picture.path))

    def test_replacing_avatar_deletes_the_old_file(self):
        user = self.make_user("alice")
        client = self.client_for(user)
        client.patch("/api/auth/profile/", {"profile_picture": png()}, format="multipart")
        user.refresh_from_db()
        old = user.profile_picture.path
        with self.captureOnCommitCallbacks(execute=True):
            client.patch("/api/auth/profile/", {"profile_picture": png()}, format="multipart")
        self.assertFalse(os.path.exists(old))

    def test_rejects_non_image_disguised_as_png(self):
        client = self.client_for(self.make_user("alice"))
        fake = SimpleUploadedFile("evil.png", b"<html><script>alert(1)</script></html>", content_type="image/png")
        r = client.patch("/api/auth/profile/", {"profile_picture": fake}, format="multipart")
        self.assertEqual(r.status_code, 400)
        self.assertIn("profile_picture", r.data)

    def test_javascript_url_rejected(self):
        client = self.client_for(self.make_user("alice"))
        r = client.patch("/api/auth/profile/", {"website_url": "javascript://x%0Aalert(1)"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_cannot_change_email_or_privileges(self):
        user = self.make_user("alice")
        r = self.client_for(user).patch(
            "/api/auth/profile/", {"email": "evil@example.com", "is_staff": True, "is_verified": False}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.email, "alice@example.com")
        self.assertFalse(user.is_staff)
        self.assertTrue(user.is_verified)

    def test_username_collision_case_insensitive(self):
        self.make_user("bob")
        r = self.client_for(self.make_user("alice")).patch("/api/auth/profile/", {"username": "BOB"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_keeping_own_username_is_fine(self):
        r = self.client_for(self.make_user("alice")).patch("/api/auth/profile/", {"username": "alice"}, format="json")
        self.assertEqual(r.status_code, 200)

    def test_deleting_user_removes_avatar_file(self):
        user = self.make_user("alice")
        self.client_for(user).patch("/api/auth/profile/", {"profile_picture": png()}, format="multipart")
        user.refresh_from_db()
        path = user.profile_picture.path
        with self.captureOnCommitCallbacks(execute=True):
            user.delete()
        self.assertFalse(os.path.exists(path))


class AdminUserTests(BaseAPITestCase):
    URL = "/api/auth/admin/users/"

    def setUp(self):
        super().setUp()
        self.admin = self.make_user("boss", is_staff=True)
        self.member = self.make_user("member")

    def test_non_staff_forbidden_and_anon_unauthorized(self):
        self.assertEqual(self.client_for(self.member).get(self.URL).status_code, 403)
        self.assertEqual(self.client.get(self.URL).status_code, 401)

    def test_list_puts_unverified_first_and_hides_nothing_needed(self):
        pending = self.make_user("pending", verified=False)
        r = self.client_for(self.admin).get(self.URL)
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.data, list)
        self.assertEqual(r.data[0]["id"], pending.id)
        for key in ("id", "username", "email", "is_staff", "is_active", "is_verified", "date_joined"):
            self.assertIn(key, r.data[0])

    def test_admin_can_verify_user(self):
        pending = self.make_user("pending", verified=False)
        r = self.client_for(self.admin).patch(
            f"{self.URL}{pending.id}/",
            {"username": "pending", "first_name": "", "last_name": "", "is_staff": False,
             "is_active": True, "is_verified": True},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.data)
        pending.refresh_from_db()
        self.assertTrue(pending.is_verified)

    def test_cannot_edit_email(self):
        r = self.client_for(self.admin).patch(f"{self.URL}{self.member.id}/", {"email": "x@y.com"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.member.refresh_from_db()
        self.assertEqual(self.member.email, "member@example.com")

    def test_cannot_delete_self_or_demote_self(self):
        client = self.client_for(self.admin)
        r = client.delete(f"{self.URL}{self.admin.id}/")
        self.assertEqual(r.status_code, 403)
        self.assertIn("detail", r.data)
        r = client.patch(f"{self.URL}{self.admin.id}/", {"is_staff": False}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_staff_cannot_touch_superuser_but_superuser_can_manage_staff(self):
        root = User.objects.create_superuser("root@example.com", "root", PASSWORD)
        self.assertEqual(self.client_for(self.admin).delete(f"{self.URL}{root.id}/").status_code, 403)
        self.assertEqual(self.client_for(self.admin).patch(f"{self.URL}{root.id}/", {"is_active": False}, format="json").status_code, 403)
        self.assertEqual(self.client_for(root).delete(f"{self.URL}{self.admin.id}/").status_code, 204)

    def test_delete_user(self):
        self.assertEqual(self.client_for(self.admin).delete(f"{self.URL}{self.member.id}/").status_code, 204)
        self.assertFalse(User.objects.filter(pk=self.member.pk).exists())

    def test_create_and_put_not_allowed(self):
        client = self.client_for(self.admin)
        self.assertEqual(client.post(self.URL, {}, format="json").status_code, 405)
        self.assertEqual(client.put(f"{self.URL}{self.member.id}/", {}, format="json").status_code, 405)


class DjangoAdminSiteTests(BaseAPITestCase):
    def test_admin_pages_render(self):
        root = User.objects.create_superuser("root@example.com", "root", PASSWORD)
        self.client.force_login(root)
        for url in ("/admin/accounts/user/", "/admin/accounts/user/add/", f"/admin/accounts/user/{root.id}/change/"):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_verify_action(self):
        root = User.objects.create_superuser("root@example.com", "root", PASSWORD)
        pending = self.make_user("pending", verified=False)
        self.client.force_login(root)
        self.client.post("/admin/accounts/user/", {"action": "verify_users", "_selected_action": [pending.pk]})
        pending.refresh_from_db()
        self.assertTrue(pending.is_verified)


class AllAdminPagesRenderTests(BaseAPITestCase):
    """Every registered model's changelist/add/change page, with real rows present.

    Guards against template/Django-version problems that only show up on pages
    with data (e.g. the post changelist with its filters and inline comments).
    """

    def test_every_admin_page_renders(self):
        from django.contrib import admin as dj_admin
        from django.urls import reverse

        from blog.models import Comment, Like, Post
        from reviews.models import Review

        root = User.objects.create_superuser("root@example.com", "root", PASSWORD)
        member = self.make_user("member")
        post = Post.objects.create(author=member, title="Hello", content="x", category="travel")
        Post.objects.create(author=member, title="Draft", content="y", is_published=False)
        Comment.objects.create(post=post, user=root, content="c")
        Like.objects.create(post=post, user=root)
        Review.objects.create(user=member, rating=5, content="r")
        self.client.force_login(root)

        checked = 0
        for model, model_admin in dj_admin.site._registry.items():
            if model._meta.app_label not in {"accounts", "blog", "reviews"}:
                continue
            info = (model._meta.app_label, model._meta.model_name)
            urls = [reverse("admin:%s_%s_changelist" % info), reverse("admin:%s_%s_add" % info)]
            obj = model.objects.first()
            if obj is not None:
                urls.append(reverse("admin:%s_%s_change" % info, args=[obj.pk]))
            for url in urls:
                self.assertEqual(self.client.get(url).status_code, 200, url)
                checked += 1
        self.assertGreaterEqual(checked, 12)

        # filters and search on the post list
        for query in ("?is_published__exact=1", "?category=travel", "?q=hello"):
            self.assertEqual(self.client.get("/admin/blog/post/" + query).status_code, 200, query)
