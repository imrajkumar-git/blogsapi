import os

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from common.testing import PNG_BYTES, BaseAPITestCase, png

from .models import Comment, Post

POSTS = "/api/blog/posts/"


def make_post(author, title="Hello World", **extra):
    extra.setdefault("content", "Body text")
    return Post.objects.create(author=author, title=title, **extra)


class PostReadTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.alice = self.make_user("alice")
        self.bob = self.make_user("bob")
        self.staff = self.make_user("boss", is_staff=True)
        self.pub = make_post(self.alice, "Public one")
        self.draft = make_post(self.alice, "Alice draft", is_published=False)

    def slugs(self, client):
        return {p["slug"] for p in client.get(POSTS).data}

    def test_anonymous_sees_only_published(self):
        self.assertEqual(self.slugs(self.client), {self.pub.slug})

    def test_author_sees_own_drafts_others_do_not(self):
        self.assertEqual(self.slugs(self.client_for(self.alice)), {self.pub.slug, self.draft.slug})
        self.assertEqual(self.slugs(self.client_for(self.bob)), {self.pub.slug})

    def test_staff_sees_everything(self):
        self.assertEqual(self.slugs(self.client_for(self.staff)), {self.pub.slug, self.draft.slug})

    def test_draft_detail_is_404_for_others(self):
        url = f"{POSTS}{self.draft.slug}/"
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client_for(self.bob).get(url).status_code, 404)
        self.assertEqual(self.client_for(self.alice).get(url).status_code, 200)

    def test_list_shape_matches_frontend(self):
        item = self.client.get(POSTS).data[0]
        for key in ("id", "slug", "title", "excerpt", "category", "cover", "is_published",
                    "created_at", "likes_count", "comments_count", "liked_by_me"):
            self.assertIn(key, item)
        self.assertEqual(item["author"]["username"], "alice")
        self.assertNotIn("email", item["author"])
        self.assertNotIn("content", item)

    def test_detail_includes_content_and_comments(self):
        Comment.objects.create(post=self.pub, user=self.bob, content="nice")
        data = self.client.get(f"{POSTS}{self.pub.slug}/").data
        self.assertEqual(data["content"], "Body text")
        self.assertEqual(data["comments"][0]["user"]["username"], "bob")
        self.assertEqual(data["comments_count"], 1)

    def test_newest_first(self):
        newer = make_post(self.alice, "Newer")
        self.assertEqual(self.client.get(POSTS).data[0]["slug"], newer.slug)


class PostWriteTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.alice = self.make_user("alice")
        self.bob = self.make_user("bob")
        self.staff = self.make_user("boss", is_staff=True)
        self.form = {"title": "My Post", "excerpt": "short", "content": "long text",
                     "category": "travel", "is_published": "true"}

    def test_create_requires_auth(self):
        self.assertEqual(self.client.post(POSTS, self.form, format="multipart").status_code, 401)

    def test_create_multipart_with_cover(self):
        r = self.client_for(self.alice).post(POSTS, {**self.form, "cover_image": png()}, format="multipart")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["slug"], "my-post")
        self.assertEqual(r.data["author"]["username"], "alice")
        self.assertEqual(r.data["likes_count"], 0)
        self.assertFalse(r.data["liked_by_me"])
        self.assertTrue(r.data["cover"].startswith("http://testserver/media/blog/covers/"))
        self.assertTrue(r.data["cover"].endswith(".png"))
        self.assertTrue(os.path.exists(Post.objects.get().cover_image.path))

    def test_cover_is_null_without_image(self):
        r = self.client_for(self.alice).post(POSTS, self.form, format="multipart")
        self.assertIsNone(r.data["cover"])

    def test_same_title_gets_unique_slugs(self):
        client = self.client_for(self.alice)
        a = client.post(POSTS, self.form, format="multipart").data["slug"]
        b = client.post(POSTS, self.form, format="multipart").data["slug"]
        self.assertNotEqual(a, b)
        self.assertTrue(b.startswith("my-post-"))

    def test_unicode_and_symbol_only_titles(self):
        client = self.client_for(self.alice)
        r = client.post(POSTS, {**self.form, "title": "مرحبا بالعالم"}, format="multipart")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(client.get(f"{POSTS}{r.data['slug']}/").status_code, 200)
        r = client.post(POSTS, {**self.form, "title": "!!!"}, format="multipart")
        self.assertTrue(r.data["slug"].startswith("post"))

    def test_invalid_category_rejected_blank_allowed(self):
        client = self.client_for(self.alice)
        self.assertEqual(client.post(POSTS, {**self.form, "category": "nope"}, format="multipart").status_code, 400)
        self.assertEqual(client.post(POSTS, {**self.form, "category": ""}, format="multipart").status_code, 201)

    def test_missing_title_or_content_rejected(self):
        client = self.client_for(self.alice)
        r = client.post(POSTS, {"excerpt": "x"}, format="multipart")
        self.assertEqual(r.status_code, 400)
        self.assertIn("title", r.data)
        self.assertIn("content", r.data)

    def test_excerpt_over_300_rejected(self):
        r = self.client_for(self.alice).post(POSTS, {**self.form, "excerpt": "x" * 301}, format="multipart")
        self.assertEqual(r.status_code, 400)

    @override_settings(BLOG_COVER_MAX_BYTES=10)
    def test_oversized_cover_rejected_with_readable_message(self):
        r = self.client_for(self.alice).post(POSTS, {**self.form, "cover_image": png()}, format="multipart")
        self.assertEqual(r.status_code, 400)
        self.assertIn("limit", r.data["cover_image"][0])

    def test_non_image_cover_rejected_even_with_image_content_type(self):
        fake = SimpleUploadedFile("x.png", b"<svg onload=alert(1)>", content_type="image/png")
        r = self.client_for(self.alice).post(POSTS, {**self.form, "cover_image": fake}, format="multipart")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Post.objects.count(), 0)

    def test_webp_gif_avif_accepted(self):
        client = self.client_for(self.alice)
        samples = {
            "webp": b"RIFF\x00\x00\x00\x00WEBPVP8 ", "gif": b"GIF89a\x01\x00\x01\x00",
            "avif": b"\x00\x00\x00\x1cftypavif\x00\x00\x00\x00",
        }
        for ext, head in samples.items():
            f = SimpleUploadedFile(f"a.{ext}", head + b"0" * 32)
            r = client.post(POSTS, {**self.form, "cover_image": f}, format="multipart")
            self.assertEqual(r.status_code, 201, (ext, r.data))
            self.assertTrue(r.data["cover"].endswith(f".{ext}"))

    def test_patch_permissions(self):
        post = make_post(self.alice)
        url = f"{POSTS}{post.slug}/"
        self.assertEqual(self.client.patch(url, {"title": "x"}, format="json").status_code, 401)
        self.assertEqual(self.client_for(self.bob).patch(url, {"title": "x"}, format="json").status_code, 403)
        self.assertEqual(self.client_for(self.alice).patch(url, {"title": "Mine"}, format="json").status_code, 200)
        self.assertEqual(self.client_for(self.staff).patch(url, {"title": "Staff"}, format="json").status_code, 200)

    def test_slug_stays_stable_when_title_changes(self):
        post = make_post(self.alice, "Original")
        r = self.client_for(self.alice).patch(f"{POSTS}{post.slug}/", {"title": "Renamed"}, format="json")
        self.assertEqual(r.data["slug"], "original")

    def test_cannot_change_author_or_slug(self):
        post = make_post(self.alice)
        self.client_for(self.alice).patch(
            f"{POSTS}{post.slug}/", {"author": self.bob.id, "slug": "hacked"}, format="json"
        )
        post.refresh_from_db()
        self.assertEqual(post.author, self.alice)
        self.assertEqual(post.slug, "hello-world")

    def test_toggle_publish_via_json_like_the_dashboard(self):
        post = make_post(self.alice)
        r = self.client_for(self.alice).patch(f"{POSTS}{post.slug}/", {"is_published": False}, format="json")
        self.assertFalse(r.data["is_published"])
        self.assertEqual(self.client.get(POSTS).data, [])

    def test_edit_form_multipart_patch(self):
        post = make_post(self.alice)
        r = self.client_for(self.alice).patch(
            f"{POSTS}{post.slug}/",
            {"title": "T", "excerpt": "", "content": "C", "is_published": "false", "category": "food"},
            format="multipart",
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data["is_published"])
        self.assertEqual(r.data["category"], "food")

    def test_replace_and_remove_cover_delete_files(self):
        client = self.client_for(self.alice)
        slug = client.post(POSTS, {**self.form, "cover_image": png()}, format="multipart").data["slug"]
        first = Post.objects.get(slug=slug).cover_image.path
        with self.captureOnCommitCallbacks(execute=True):
            client.patch(f"{POSTS}{slug}/", {"cover_image": png()}, format="multipart")
        self.assertFalse(os.path.exists(first))
        second = Post.objects.get(slug=slug).cover_image.path
        self.assertTrue(os.path.exists(second))
        with self.captureOnCommitCallbacks(execute=True):
            r = client.patch(f"{POSTS}{slug}/", {"remove_cover_image": "true"}, format="multipart")
        self.assertIsNone(r.data["cover"])
        self.assertFalse(os.path.exists(second))

    def test_delete_post_permissions_and_cover_cleanup(self):
        client = self.client_for(self.alice)
        slug = client.post(POSTS, {**self.form, "cover_image": png()}, format="multipart").data["slug"]
        path = Post.objects.get(slug=slug).cover_image.path
        self.assertEqual(self.client_for(self.bob).delete(f"{POSTS}{slug}/").status_code, 403)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(client.delete(f"{POSTS}{slug}/").status_code, 204)
        self.assertFalse(os.path.exists(path))

    def test_staff_can_delete_any_post(self):
        post = make_post(self.alice)
        self.assertEqual(self.client_for(self.staff).delete(f"{POSTS}{post.slug}/").status_code, 204)


class LikeAndCommentTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.alice = self.make_user("alice")
        self.bob = self.make_user("bob")
        self.staff = self.make_user("boss", is_staff=True)
        self.post = make_post(self.alice)
        self.base = f"{POSTS}{self.post.slug}/"

    def test_like_toggles_and_counts(self):
        bob = self.client_for(self.bob)
        r = bob.post(f"{self.base}like/")
        self.assertEqual(r.data, {"liked_by_me": True, "likes_count": 1})
        self.assertTrue(bob.get(self.base).data["liked_by_me"])
        self.assertFalse(self.client.get(self.base).data["liked_by_me"])
        self.assertEqual(self.client_for(self.alice).post(f"{self.base}like/").data["likes_count"], 2)
        r = bob.post(f"{self.base}like/")
        self.assertEqual(r.data, {"liked_by_me": False, "likes_count": 1})
        self.assertEqual(self.client.get(POSTS).data[0]["likes_count"], 1)

    def test_like_requires_auth(self):
        self.assertEqual(self.client.post(f"{self.base}like/").status_code, 401)

    def test_cannot_like_someone_elses_draft(self):
        draft = make_post(self.alice, "Secret", is_published=False)
        self.assertEqual(self.client_for(self.bob).post(f"{POSTS}{draft.slug}/like/").status_code, 404)

    def test_comment_flow(self):
        bob = self.client_for(self.bob)
        r = bob.post(f"{self.base}comments/", {"content": "Great post"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["user"]["username"], "bob")
        self.assertIn("id", r.data)
        self.assertEqual(self.client.get(self.base).data["comments_count"], 1)
        self.assertEqual(len(self.client.get(f"{self.base}comments/").data), 1)

    def test_comment_requires_auth_and_content(self):
        self.assertEqual(self.client.post(f"{self.base}comments/", {"content": "x"}, format="json").status_code, 401)
        self.assertEqual(self.client_for(self.bob).post(f"{self.base}comments/", {"content": "  "}, format="json").status_code, 400)

    def test_comment_delete_permissions(self):
        c = Comment.objects.create(post=self.post, user=self.bob, content="hi")
        url = f"/api/blog/comments/{c.id}/"
        self.assertEqual(self.client.delete(url).status_code, 401)
        self.assertEqual(self.client_for(self.alice).delete(url).status_code, 403)
        self.assertEqual(self.client_for(self.bob).delete(url).status_code, 204)
        c2 = Comment.objects.create(post=self.post, user=self.bob, content="hi")
        self.assertEqual(self.client_for(self.staff).delete(f"/api/blog/comments/{c2.id}/").status_code, 204)
