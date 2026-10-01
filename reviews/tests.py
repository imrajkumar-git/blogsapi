from common.testing import BaseAPITestCase

from .models import Review

URL = "/api/reviews/"


class ReviewTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.alice = self.make_user("alice")
        self.bob = self.make_user("bob")
        self.staff = self.make_user("boss", is_staff=True)

    def test_list_is_public_and_shaped_for_frontend(self):
        Review.objects.create(user=self.alice, rating=4, content="good")
        r = self.client.get(URL)
        self.assertEqual(r.status_code, 200)
        item = r.data[0]
        self.assertEqual(item["user"]["username"], "alice")
        self.assertNotIn("email", item["user"])
        for key in ("id", "rating", "content", "created_at"):
            self.assertIn(key, item)

    def test_create_requires_auth(self):
        self.assertEqual(self.client.post(URL, {"rating": 5, "content": "x"}, format="json").status_code, 401)

    def test_post_creates_then_updates_same_row(self):
        client = self.client_for(self.alice)
        r = client.post(URL, {"rating": 5, "content": "great"}, format="json")
        self.assertEqual(r.status_code, 201)
        first_id = r.data["id"]
        r = client.post(URL, {"rating": 3, "content": "meh"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["id"], first_id)
        self.assertEqual(r.data["rating"], 3)
        self.assertEqual(Review.objects.count(), 1)

    def test_rating_bounds_and_content_required(self):
        client = self.client_for(self.alice)
        for bad in ({"rating": 0, "content": "x"}, {"rating": 6, "content": "x"},
                    {"rating": 5, "content": ""}, {"rating": 5}, {"content": "x"}):
            self.assertEqual(client.post(URL, bad, format="json").status_code, 400, bad)

    def test_mine_is_json_null_when_no_review(self):
        r = self.client_for(self.alice).get(URL + "mine/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, b"null")

    def test_mine_returns_own_review(self):
        Review.objects.create(user=self.alice, rating=2, content="a")
        Review.objects.create(user=self.bob, rating=5, content="b")
        r = self.client_for(self.alice).get(URL + "mine/")
        self.assertEqual(r.data["rating"], 2)

    def test_mine_requires_auth(self):
        self.assertEqual(self.client.get(URL + "mine/").status_code, 401)

    def test_delete_permissions(self):
        review = Review.objects.create(user=self.alice, rating=4, content="x")
        url = f"{URL}{review.id}/"
        self.assertEqual(self.client.delete(url).status_code, 401)
        self.assertEqual(self.client_for(self.bob).delete(url).status_code, 403)
        self.assertEqual(self.client_for(self.staff).delete(url).status_code, 204)
        mine = Review.objects.create(user=self.bob, rating=1, content="y")
        self.assertEqual(self.client_for(self.bob).delete(f"{URL}{mine.id}/").status_code, 204)
