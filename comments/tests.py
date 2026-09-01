from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from captcha.fields import CaptchaField

from .forms import CommentForm, sanitize_comment_html
from .models import Comment
from .views import get_parent_comment


class CommentTestMixin:
    """Общие данные для тестов CommentForm."""

    valid_data = {
        "user_name": "TestUser123",
        "email": "test@example.com",
        "home_page": "",
        "text": "Hello world",
        "captcha_0": "test-key",
        "captcha_1": "PASSED",
    }

    captcha_patch = patch.object(
        CaptchaField,
        "clean",
        return_value="PASSED",
    )


class CommentFormValidationTests(CommentTestMixin, TestCase):
    """Проверяем серверную валидацию основной формы."""

    def make_form(self, **overrides):
        data = self.valid_data.copy()
        data.update(overrides)

        return CommentForm(data=data)

    def test_valid_form_is_valid(self):
        with self.captcha_patch:
            form = self.make_form()

            self.assertTrue(form.is_valid(), form.errors)

    def test_invalid_email_is_rejected(self):
        invalid_emails = [
            "test",
            "test@",
            "@example.com",
            "test@@example.com",
            "test@example",
        ]

        for email in invalid_emails:
            with self.subTest(email=email), self.captcha_patch:
                form = self.make_form(email=email)

                self.assertFalse(form.is_valid())
                self.assertIn("email", form.errors)

    def test_valid_email_is_accepted(self):
        valid_emails = [
            "test@example.com",
            "john.smith@example.org",
            "user+tag@example.co.uk",
        ]

        for email in valid_emails:
            with self.subTest(email=email), self.captcha_patch:
                form = self.make_form(email=email)

                self.assertNotIn("email", form.errors)
                self.assertTrue(
                    form.is_valid(),
                    form.errors,
                )

    def test_invalid_username_is_rejected(self):
        invalid_names = [
            "юзер",
            "user name",
            "user-name",
            "user_name",
            "user!",
        ]

        for user_name in invalid_names:
            with self.subTest(user_name=user_name), self.captcha_patch:
                form = self.make_form(user_name=user_name)

                self.assertFalse(form.is_valid())
                self.assertIn("user_name", form.errors)

    def test_empty_required_fields_are_rejected(self):
        with self.captcha_patch:
            form = self.make_form(
                user_name="",
                email="",
                text="",
            )

            self.assertFalse(form.is_valid())
            self.assertIn("user_name", form.errors)
            self.assertIn("email", form.errors)
            self.assertIn("text", form.errors)

    def test_invalid_url_is_rejected(self):
        invalid_urls = [
            "javascript:alert(1)",
            "ftp://example.com",
        ]

        for url in invalid_urls:
            with self.subTest(url=url), self.captcha_patch:
                form = self.make_form(home_page=url)

                self.assertFalse(form.is_valid())
                self.assertIn("home_page", form.errors)

    def test_valid_urls_are_accepted(self):
        valid_urls = [
            "http://example.com",
            "https://example.com",
        ]

        for url in valid_urls:
            with self.subTest(url=url), self.captcha_patch:
                form = self.make_form(home_page=url)

                self.assertTrue(
                    form.is_valid(),
                    form.errors,
                )

    def test_text_is_required(self):
        with self.captcha_patch:
            form = self.make_form(text="   ")

            self.assertFalse(form.is_valid())
            self.assertIn("text", form.errors)

    def test_text_length_limit(self):
        with self.captcha_patch:
            form = self.make_form(text="a" * 5001)

            self.assertFalse(form.is_valid())
            self.assertIn("text", form.errors)

    def test_unclosed_html_tag_is_rejected(self):
        with self.captcha_patch:
            form = self.make_form(
                text="<strong>Hello"
            )

            self.assertFalse(form.is_valid())
            self.assertIn("text", form.errors)

    def test_mismatched_html_tags_are_rejected(self):
        with self.captcha_patch:
            form = self.make_form(
                text="<strong>Hello</i>"
            )

            self.assertFalse(form.is_valid())
            self.assertIn("text", form.errors)

    def test_disallowed_html_tag_is_rejected(self):
        with self.captcha_patch:
            form = self.make_form(
                text="<script>alert(1)</script>"
            )

            self.assertFalse(form.is_valid())
            self.assertIn("text", form.errors)

    def test_allowed_html_is_preserved(self):
        with self.captcha_patch:
            form = self.make_form(
                text="<strong>Hello</strong>"
            )

            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(
                form.cleaned_data["text"],
                "<strong>Hello</strong>",
            )


class XssSanitizationTests(TestCase):
    """Проверяем очистку опасного HTML."""

    def test_script_tag_is_removed(self):
        result = sanitize_comment_html(
            "<script>alert(1)</script>Hello"
        )

        self.assertNotIn("<script>", result)
        self.assertNotIn("</script>", result)
        self.assertIn("Hello", result)

    def test_javascript_href_is_not_allowed(self):
        result = sanitize_comment_html(
            '<a href="javascript:alert(1)" title="x">link</a>'
        )

        self.assertNotIn("javascript:", result)

    def test_event_handler_is_not_allowed(self):
        result = sanitize_comment_html(
            '<strong onclick="alert(1)">Hello</strong>'
        )

        self.assertNotIn("onclick", result)
        self.assertIn("Hello", result)

    def test_iframe_is_not_allowed(self):
        result = sanitize_comment_html(
            '<iframe src="https://evil.example"></iframe>'
        )

        self.assertNotIn("<iframe", result)
        self.assertNotIn("</iframe>", result)


class AttachmentValidationTests(CommentTestMixin, TestCase):
    """Проверяем загрузку файлов."""

    def make_form(self, uploaded_file, **overrides):
        data = self.valid_data.copy()
        data.update(overrides)

        return CommentForm(
            data=data,
            files={"attachment": uploaded_file},
        )

    def create_image(
        self,
        width=100,
        height=100,
        image_format="JPEG",
        name="test.jpg",
    ):
        buffer = BytesIO()

        image = Image.new(
            "RGB",
            (width, height),
        )
        image.save(buffer, format=image_format)

        return SimpleUploadedFile(
            name=name,
            content=buffer.getvalue(),
            content_type=f"image/{image_format.lower()}",
        )

    def test_valid_jpg_is_accepted(self):
        uploaded = self.create_image()

        with self.captcha_patch:
            form = self.make_form(uploaded)

            self.assertTrue(
                form.is_valid(),
                form.errors,
            )

    def test_large_image_is_resized(self):
        uploaded = self.create_image(
            width=1200,
            height=900,
        )

        with self.captcha_patch:
            form = self.make_form(uploaded)

            self.assertTrue(
                form.is_valid(),
                form.errors,
            )

            cleaned_file = form.cleaned_data["attachment"]
            cleaned_file.seek(0)

            image = Image.open(cleaned_file)

            self.assertLessEqual(image.width, 320)
            self.assertLessEqual(image.height, 240)

    def test_invalid_image_content_is_rejected(self):
        uploaded = SimpleUploadedFile(
            name="fake.jpg",
            content=b"this is not an image",
            content_type="image/jpeg",
        )

        with self.captcha_patch:
            form = self.make_form(uploaded)

            self.assertFalse(form.is_valid())
            self.assertIn("attachment", form.errors)

    def test_invalid_extension_is_rejected(self):
        uploaded = SimpleUploadedFile(
            name="virus.exe",
            content=b"fake executable",
            content_type="application/octet-stream",
        )

        with self.captcha_patch:
            form = self.make_form(uploaded)

            self.assertFalse(form.is_valid())
            self.assertIn("attachment", form.errors)

    def test_txt_over_100_kb_is_rejected(self):
        uploaded = SimpleUploadedFile(
            name="large.txt",
            content=b"a" * (100 * 1024 + 1),
            content_type="text/plain",
        )

        with self.captcha_patch:
            form = self.make_form(uploaded)

            self.assertFalse(form.is_valid())
            self.assertIn("attachment", form.errors)


class CommentViewTests(CommentTestMixin, TestCase):
    """Проверяем HTTP-поведение views."""

    def setUp(self):
        self.url = reverse("comment_list")

    def test_invalid_email_does_not_create_comment(self):
        data = self.valid_data.copy()
        data["email"] = "invalid-email"

        with self.captcha_patch, patch(
            "comments.views.notify_new_comment"
        ):
            response = self.client.post(
                self.url,
                data=data,
            )

        self.assertEqual(response.status_code, 200)

        form = response.context["form"]

        self.assertIn("email", form.errors)

        self.assertEqual(
            Comment.objects.count(),
            0,
        )

    def test_valid_comment_is_created(self):
        with self.captcha_patch, patch(
            "comments.views.notify_new_comment"
        ):
            response = self.client.post(
                self.url,
                data=self.valid_data,
            )

        self.assertRedirects(
            response,
            reverse("comment_list"),
        )

        self.assertEqual(
            Comment.objects.count(),
            1,
        )

        comment = Comment.objects.get()

        self.assertEqual(
            comment.email,
            "test@example.com",
        )
        self.assertEqual(
            comment.user_name,
            "TestUser123",
        )

    def test_invalid_email_is_not_saved_to_database(self):
        data = self.valid_data.copy()
        data["email"] = "not-an-email"

        with self.captcha_patch, patch(
            "comments.views.notify_new_comment"
        ):
            self.client.post(
                self.url,
                data=data,
            )

        self.assertFalse(
            Comment.objects.filter(
                email="not-an-email"
            ).exists()
        )

    def test_pagination_contains_25_comments(self):
        Comment.objects.bulk_create(
            [
                Comment(
                    user_name=f"User{i}",
                    email=f"user{i}@example.com",
                    text=f"Comment {i}",
                )
                for i in range(30)
            ]
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            len(response.context["comments"].object_list),
            25,
        )
        self.assertEqual(
            response.context["comments"].paginator.num_pages,
            2,
        )

    def test_sorting_by_user_name_ascending(self):
        Comment.objects.create(
            user_name="Zed",
            email="zed@example.com",
            text="Zed comment",
        )
        Comment.objects.create(
            user_name="Adam",
            email="adam@example.com",
            text="Adam comment",
        )

        response = self.client.get(
            self.url,
            {
                "sort": "user_name",
                "direction": "asc",
            },
        )

        comments = list(
            response.context["comments"].object_list
        )

        self.assertEqual(
            [comment.user_name for comment in comments],
            ["Adam", "Zed"],
        )

    def test_sorting_by_email_descending(self):
        Comment.objects.create(
            user_name="A",
            email="a@example.com",
            text="A",
        )
        Comment.objects.create(
            user_name="B",
            email="b@example.com",
            text="B",
        )

        response = self.client.get(
            self.url,
            {
                "sort": "email",
                "direction": "desc",
            },
        )

        comments = list(
            response.context["comments"].object_list
        )

        self.assertEqual(
            [comment.email for comment in comments],
            ["b@example.com", "a@example.com"],
        )

    def test_default_sorting_is_lifo(self):
        first = Comment.objects.create(
            user_name="First",
            email="first@example.com",
            text="First",
        )
        second = Comment.objects.create(
            user_name="Second",
            email="second@example.com",
            text="Second",
        )

        response = self.client.get(self.url)

        comments = list(
            response.context["comments"].object_list
        )

        self.assertEqual(
            comments[0].id,
            second.id,
        )
        self.assertEqual(
            comments[1].id,
            first.id,
        )

    def test_comment_preview_rejects_invalid_html(self):
        response = self.client.post(
            reverse("comment_preview"),
            {
                "text": "<strong>Hello",
            },
        )

        self.assertEqual(
            response.status_code,
            400,
        )

        self.assertIn(
            "error",
            response.json(),
        )

    def test_comment_preview_returns_sanitized_html(self):
        response = self.client.post(
            reverse("comment_preview"),
            {
                "text": "<strong>Hello</strong>",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.json()["html"],
            "<strong>Hello</strong>",
        )

    def test_comment_preview_only_allows_post(self):
        response = self.client.get(
            reverse("comment_preview")
        )

        self.assertEqual(
            response.status_code,
            405,
        )


class ReplyTests(CommentTestMixin, TestCase):
    """Проверяем каскадные ответы."""

    def setUp(self):
        self.url = reverse("comment_list")

        self.parent = Comment.objects.create(
            user_name="Parent",
            email="parent@example.com",
            text="Parent comment",
        )

    def test_reply_is_created_for_existing_parent(self):
        data = self.valid_data.copy()
        data["user_name"] = "ReplyUser"
        data["email"] = "reply@example.com"
        data["text"] = "Reply text"
        data["parent_id"] = str(self.parent.id)

        with self.captcha_patch, patch(
            "comments.views.notify_new_comment"
        ):
            response = self.client.post(
                self.url,
                data=data,
            )

        self.assertRedirects(
            response,
            reverse("comment_list"),
        )

        reply = Comment.objects.get(
            user_name="ReplyUser"
        )

        self.assertEqual(
            reply.parent_id,
            self.parent.id,
        )

    def test_invalid_parent_id_does_not_crash(self):
        response = self.client.post(
            self.url,
            {
                **self.valid_data,
                "parent_id": "999999999999999999999999999999",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )


class GetParentCommentTests(TestCase):
    """Проверяем безопасную обработку parent_id."""

    def test_none_for_non_digit(self):
        self.assertIsNone(
            get_parent_comment("abc")
        )

    def test_none_for_empty(self):
        self.assertIsNone(
            get_parent_comment("")
        )

    def test_none_for_bigint_overflow(self):
        self.assertIsNone(
            get_parent_comment(
                "999999999999999999999999999999"
            )
        )

    def test_returns_existing_comment(self):
        comment = Comment.objects.create(
            user_name="User123",
            email="user@example.com",
            text="Hello",
        )

        result = get_parent_comment(
            str(comment.id)
        )

        self.assertEqual(
            result.id,
            comment.id,
        )