import shutil
import tempfile
from http import HTTPStatus

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ..models import Comment, Group, Post

User = get_user_model()

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
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
        cls.post_reverse_url = reverse("posts:post_edit", args=[cls.post.id])

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

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

    def test_send_post_with_image(self):
        response = self.auth_client.get(reverse("posts:post_create"))
        form_fields = {
            "group": forms.fields.ChoiceField,
            "text": forms.fields.CharField,
            "image": forms.fields.ImageField,
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context["form"].fields[value]
                self.assertIsInstance(form_field, expected)

    def test_authorized_user_can_write_comment(self):
        comment_count = Comment.objects.count()
        form_data = {"text": self.post.text}
        kwargs = {"post_id": self.post.id}
        response = self.auth_client.post(
            reverse("posts:add_comment", kwargs=kwargs),
            data=form_data,
            follow=True,
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(Comment.objects.count(), comment_count + 1)
        self.assertRedirects(
            response, reverse("posts:post_detail", kwargs=kwargs)
        )
        self.assertTrue(
            Comment.objects.filter(
                text=self.post.text,
                author=self.user,
                post=self.post,
            )
        )
        last_comment = Comment.objects.order_by("-id").first()
        self.assertEqual(form_data["text"], last_comment.text)
        self.assertEqual(self.user, last_comment.author)
        self.assertEqual(self.post, last_comment.post)

    def test_unauthorized_user_cannot_write_comment(self):
        comment_count = Comment.objects.count()
        form_data = {"text": self.post.text}
        kwargs = {"post_id": self.post.id}
        response = self.non_auth_client.post(
            reverse("posts:add_comment", kwargs=kwargs),
            data=form_data,
            follow=True,
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertNotEqual(Comment.objects.count(), comment_count + 1)
        self.assertRedirects(
            response,
            f"{reverse('users:login')}?next={reverse('posts:add_comment', kwargs=kwargs)}",
        )
