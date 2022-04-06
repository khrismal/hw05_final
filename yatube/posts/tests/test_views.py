import shutil
import tempfile
from http import HTTPStatus

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ..models import Follow, Group, Post, User

User = get_user_model()

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostPagesTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username="username")
        cls.another_user = User.objects.create_user(
            username="another_username"
        )
        cls.group = Group.objects.create(
            title="Тестовая группа",
            slug="test-slug",
            description="Тестовое описание",
        )

        image = (
            b"\x47\x49\x46\x38\x39\x61\x02\x00"
            b"\x01\x00\x80\x00\x00\x00\x00\x00"
            b"\xFF\xFF\xFF\x21\xF9\x04\x00\x00"
            b"\x00\x00\x00\x2C\x00\x00\x00\x00"
            b"\x02\x00\x01\x00\x00\x02\x02\x0C"
            b"\x0A\x00\x3B"
        )
        cls.test_image = SimpleUploadedFile(
            name="image.gif", content=image, content_type="image/gif"
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text="Тестовый текст",
            group=cls.group,
            image=cls.test_image,
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        self.another_authorized_client = Client()
        self.another_authorized_client.force_login(self.another_user)

    def test_pages_use_correct_template(self):
        templates_pages_names = {
            "posts/index.html": reverse("posts:index"),
            "posts/group_list.html": reverse(
                "posts:group_list", kwargs={"slug": self.group.slug}
            ),
            "posts/post_detail.html": reverse(
                "posts:post_detail", kwargs={"post_id": self.post.id}
            ),
            "posts/profile.html": reverse(
                "posts:profile",
                kwargs={"username": PostPagesTests.post.author},
            ),
            "posts/create_post.html": reverse("posts:post_create"),
            "posts/update_post.html": reverse(
                "posts:post_edit",
                kwargs={"post_id": PostPagesTests.post.id},
            ),
        }
        for template, reverse_name in templates_pages_names.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_client.get(reverse_name)
                self.assertTemplateUsed(response, template)

    def index_group_profile_show_correct_context(self):
        pages = [
            ["posts:index", {}],
            ["posts:group_list", {"slug": self.group.slug}],
            [
                "posts:profile",
                {"username": self.user},
            ],
        ]
        for page, kw in pages:
            response = self.guest_client.get(reverse(page, kwargs=kw))
            self.assertEqual(len(response.context["page_obj"]), 1)
            self.assertEqual(
                response.context["page_obj"][0].image, self.post.image
            )

    def test_post_detail_show_correct_context(self):
        post = Post.objects.first()
        response = self.authorized_client.get(
            reverse("posts:post_detail", kwargs={"post_id": post.id})
        )
        post_var = response.context["post"]
        self.assertEqual(post_var.text, self.post.text)
        self.assertEqual(post_var.image, self.post.image)

    def test_post_edit_show_correct_context(self):
        response = self.authorized_client.get(
            reverse(
                "posts:post_edit", kwargs={"post_id": PostPagesTests.post.id}
            )
        )
        form_fields = {
            PostPagesTests.post.text: response.context["form"]["text"].value(),
            PostPagesTests.post.group.id: response.context["form"][
                "group"
            ].value(),
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                self.assertEqual(value, expected)

    def test_create_post_show_correct_context(self):
        response = self.authorized_client.get(reverse("posts:post_create"))
        form_fields = {
            "text": forms.fields.CharField,
            "group": forms.fields.ChoiceField,
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get("form").fields.get(value)
            self.assertIsInstance(form_field, expected)

    def test_404_return_custom_templates(self):
        response = self.guest_client.get("not_found").status_code
        self.assertEqual(response, HTTPStatus.NOT_FOUND, "Ошибка 404 страницы")

    def test_cache_index_page(self):
        response = self.authorized_client.get(reverse("posts:index"))
        content = response.content
        Post.objects.all().delete()
        response = self.authorized_client.get(reverse("posts:index"))
        self.assertEqual(content, response.content)
        cache.clear()
        response = self.authorized_client.get(reverse("posts:index"))
        self.assertNotEqual(content, response.content)

    def test_autorized_user_can_follow(self):
        follower_count = Follow.objects.count()
        self.authorized_client.post(
            reverse(
                "posts:profile_follow", kwargs={"username": self.another_user}
            )
        )
        self.assertTrue(
            Follow.objects.filter(
                user=self.user, author=self.another_user
            ).exists()
        )
        self.assertEqual(Follow.objects.count(), follower_count + 1)
        follower = Follow.objects.order_by("-id").first()  # свежая запись
        self.assertEqual(follower.user, self.user)
        self.assertEqual(follower.author, self.another_user)

    def test_autorized_user_can_unfollow(self):
        Follow.objects.create(user=self.user, author=self.another_user)
        follower_count = Follow.objects.count()
        self.authorized_client.post(
            reverse(
                "posts:profile_unfollow",
                kwargs={"username": self.another_user},
            )
        )
        self.assertFalse(
            Follow.objects.filter(
                user=self.user, author=self.another_user
            ).exists()
        )
        self.assertEqual(Follow.objects.count(), follower_count - 1)

    def test_new_post_for_followers(self):
        response = self.authorized_client.get(reverse("posts:follow_index"))
        post_count = len(response.context["page_obj"])
        Post.objects.create(
            author=self.another_user,
            text=self.post.text,
        )
        Follow.objects.create(user=self.user, author=self.another_user)
        response = self.authorized_client.get(
            reverse("posts:follow_index")
        )  # обновление
        self.assertEqual(len(response.context["page_obj"]), post_count + 1)

    def test_new_post_for_unfollowers(self):
        response = self.authorized_client.get(reverse("posts:follow_index"))
        post_count = len(response.context["page_obj"])
        Follow.objects.filter(author=self.another_user).delete()
        Post.objects.create(
            author=self.another_user,
            text=self.post.text,
        )
        response = self.authorized_client.get(
            reverse("posts:follow_index")
        )  # обновление
        self.assertEqual(len(response.context["page_obj"]), post_count)


class PaginatorViewsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username="username")
        cls.group = Group.objects.create(
            title="Тестовый заголовок",
            slug="test-slug",
            description="Тестовое описание",
        )

        bulk_list = list()
        for x in range(13):
            bulk_list.append(
                Post(author=cls.user, text="Тестовый текст", group=cls.group)
            )
        Post.objects.bulk_create(bulk_list)

    def setUp(self):
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def test_index_group_list_profile_contains_ten_records(self):
        paths = [
            ["posts:index", {}],
            ["posts:group_list", {"slug": self.group.slug}],
            ["posts:profile", {"username": self.user}],
        ]
        for path, kw in paths:
            response = self.guest_client.get(reverse(path, kwargs=kw))
            self.assertEqual(
                len(response.context["page_obj"]), settings.PAGE_NUM
            )

    def test_index_group_list_profile_second_contains_three_records(self):
        posts_number = Post.objects.all().count()
        paths = [
            ["posts:index", {}],
            ["posts:group_list", {"slug": self.group.slug}],
            ["posts:profile", {"username": self.user}],
        ]
        for path, kw in paths:
            response = self.guest_client.get(
                reverse(path, kwargs=kw) + "?page=2"
            )
            self.assertEqual(
                len(response.context["page_obj"]),
                min(posts_number - settings.PAGE_NUM, settings.PAGE_NUM),
            )
