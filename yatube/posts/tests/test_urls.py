# posts/tests/test_urls.py
from http import HTTPStatus

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from ..models import Group, Post

User = get_user_model()


class StaticURLTests(TestCase):
    def setUp(self):
        self.guest_client = Client()

    def test_static_pages_exist_at_desired_location(self):
        paths = [
            "/about/author/",
            "/about/tech/",
        ]
        for path in paths:
            response = self.guest_client.get(path)
            self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_about_author_uses_correct_template(self):
        response = self.guest_client.get("/about/author/")
        self.assertTemplateUsed(response, "about/author.html")

    def test_about_tech_uses_correct_template(self):
        response = self.guest_client.get("/about/tech/")
        self.assertTemplateUsed(response, "about/tech.html")


class PostURLTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username="username")
        cls.group = Group.objects.create(
            title="Тестовая группа",
            slug="slug",
            description="Тестовое описание",
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text="Тестовый текст",
        )

    def setUp(self):
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def test_all_exists_at_desired_location(self):
        paths = [
            "/",
            "/group/slug/",
            "/profile/username/",
            f"/posts/{self.post.id}/",
        ]
        for path in paths:
            response = self.guest_client.get(path)
            self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_post_detail_exists_at_desired_location(self):
        response = self.guest_client.get(f"/posts/{self.post.id}/")
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_posts_edit_url_exists_at_desired_location_authorized(self):
        response = self.authorized_client.get(f"/posts/{self.post.id}/edit/")
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_posts_create_url_exists_at_desired_location_authorized(self):
        response = self.authorized_client.get("/create/")
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_create_redirect_anonymous_on_login(self):
        response = self.guest_client.get("/create/", follow=True)
        self.assertRedirects(response, "/auth/login/?next=/create/")

    def test_edit_redirect_anonymous_on_login(self):
        response = self.guest_client.get("/posts/1/edit/", follow=True)
        self.assertRedirects(
            response,
            "/auth/login/?next=/posts/1/edit/",
        )

    def test_unexisting_page_url_exists_at_desired_location(self):
        response = self.guest_client.get("/posts/404/")
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_urls_uses_correct_template(self):
        templates_url_names = {
            "posts/index.html": "/",
            "posts/group_list.html": "/group/slug/",
            "posts/profile.html": "/profile/username/",
            "posts/post_detail.html": f"/posts/{self.post.id}/",
            "posts/create_post.html": "/create/",
            "posts/update_post.html": f"/posts/{self.post.id}/edit/",
        }
        for template, address in templates_url_names.items():
            with self.subTest(address=address):
                response = self.authorized_client.get(address)
                self.assertTemplateUsed(response, template)
