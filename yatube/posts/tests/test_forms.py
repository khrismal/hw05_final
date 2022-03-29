from http import HTTPStatus

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from ..models import Group, Post

User = get_user_model()


class PostCreateFormTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username="username")
        cls.group = Group.objects.create(
            title="Тестовая группа",
            slug="test-slug",
            description="Тестовое описание",
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text="Тестовый текст",
            group=cls.group,
        )
        cls.post_reverse_url = reverse("posts:post_edit", args=[cls.post.id])

    def setUp(self):
        self.non_auth_client = Client()
        self.auth_client = Client()
        self.auth_client.force_login(self.user)

    def test_new_post_create(self):
        posts_count = Post.objects.count()
        post_form = {
            "text": self.post.text,
            "group": self.group.id,
        }
        response = self.auth_client.post(
            reverse("posts:post_create"),
            data=post_form,
        )

        self.assertEqual(Post.objects.count(), posts_count + 1)
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        new_post = Post.objects.first()
        self.assertEqual(new_post.text, self.post.text)
        self.assertEqual(new_post.author, self.user)
        self.assertEqual(new_post.group.slug, self.group.slug)

    def test_changes_in_post_edit(self):
        posts_count = Post.objects.count()
        post_form = {
            "text": self.post.text,
            "group": self.group.id,
        }
        response = self.auth_client.post(
            self.post_reverse_url, data=post_form, follow=True
        )
        changed_post = Post.objects.get(pk=self.post.id)
        self.assertEqual(changed_post.text, self.post.text)
        self.assertEqual(Post.objects.count(), posts_count)
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def create_post_by_not_author_user(self):
        posts_count = Post.objects.count()
        post_form = {
            "text": self.post.text,
            "group": self.group.id,
        }
        response = self.non_auth_client.post(
            reverse("posts:post_create"),
            data=post_form,
        )

        self.assertEqual(Post.objects.count(), posts_count)
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertRedirects(
            response,
            f"{reverse('users:login')}?next={reverse('posts:post_create')}",
        )
