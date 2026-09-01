from django import forms
from .models import Comment
from captcha.fields import CaptchaField
import re
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlsplit
from PIL import Image, UnidentifiedImageError
from django.core.files.base import ContentFile


ALLOWED_TAGS = {'a', 'code', 'i', 'strong'}


class CommentHTMLValidator(HTMLParser):

    allowed_tags = {'a', 'code', 'i', 'strong'}

    def __init__(self):
        super().__init__()
        self.errors = []
        self.stack = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.allowed_tags:
            self.errors.append(f'Тег <{tag}> запрещён.')
            return

        attrs = dict(attrs)

        if tag == 'a':
            if set(attrs.keys()) - {'href', 'title'}:
                self.errors.append(
                    'У тега <a> разрешены только href и title.'
                )

            if 'href' not in attrs or 'title' not in attrs:
                self.errors.append(
                    'У тега <a> должны быть href и title.'
                )

        elif attrs:
            self.errors.append(
                f'У тега <{tag}> атрибуты не разрешены.'
            )

        self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.errors.append(
            f'Самозакрывающийся тег <{tag}/> запрещён.'
        )

    def handle_endtag(self, tag):
        if tag not in self.allowed_tags:
            self.errors.append(f'Тег </{tag}> запрещён.')
            return

        if not self.stack:
            self.errors.append(
                f'Закрывающий тег </{tag}> не имеет пары.'
            )
            return

        if self.stack[-1] != tag:
            self.errors.append(
                f'Неправильное закрытие тега </{tag}>.'
            )
            return

        self.stack.pop()

    def validate(self):
        if self.stack:
            self.errors.append(
                f'Не закрыт тег <{self.stack[-1]}>.'
            )

        if self.errors:
            raise ValueError(' '.join(self.errors))
        

class CommentHTMLSanitizer(HTMLParser):
    """Allow the four tags from the specification and escape everything else."""
    
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.output = []
        self.open_tags = []

    def handle_data(self, data):
        self.output.append(escape(data))

    def handle_starttag(self, tag, attrs):
        # Разрешаем только теги из списка
        if tag not in ALLOWED_TAGS:
            return

        # Запрещаем вложение разрешенных тегов друг в друга (валидный XHTML)
        if self.open_tags and self.open_tags[-1] in ALLOWED_TAGS:
            # Игнорируем вложенный тег (выводим как обычный текст)
            return

        if tag == "a":
            values = dict(attrs)
            href = values.get("href", "").strip()
            attributes = ""

            # Добавляем href только если он есть и безопасен
            if href:
                scheme = urlsplit(href).scheme.lower()
                if scheme not in {"http", "https", "mailto"}:
                    return  # Небезопасная ссылка — пропускаем весь тег
                attributes += f' href="{escape(href, quote=True)}"'

            # Добавляем title, если есть
            title = values.get("title")
            if title is not None:
                attributes += f' title="{escape(title, quote=True)}"'

            self.output.append(f"<a{attributes}>")
        else:
            # code, i, strong — без атрибутов
            self.output.append(f"<{tag}>")

        self.open_tags.append(tag)

    def handle_endtag(self, tag):
        # Если тег не был открыт — игнорируем
        if tag not in self.open_tags:
            return

        # Проверяем, что закрываем последний открытый тег (валидный XHTML)
        if self.open_tags[-1] != tag:
            # Невалидный вложенный тег — просто закрываем его
            self.output.append(f"</{tag}>")
            # Удаляем тег из списка (но только если он там есть)
            if tag in self.open_tags:
                self.open_tags.remove(tag)
            return

        # Валидный случай — закрываем последний тег
        self.open_tags.pop()
        self.output.append(f"</{tag}>")

    def close(self):
        super().close()
        # Закрываем все оставшиеся открытые теги
        while self.open_tags:
            self.output.append(f"</{self.open_tags.pop()}>")


def sanitize_comment_html(value):
    """Очищает HTML от небезопасных тегов и атрибутов."""
    parser = CommentHTMLSanitizer()
    parser.feed(value)
    parser.close()
    return "".join(parser.output)


class CommentForm(forms.ModelForm):
    captcha = CaptchaField()

    class Meta:
        model = Comment
        fields = [
            'user_name',
            'email',
            'home_page',
            'text',
            'attachment', 
        ]
        widgets = {
            'text': forms.Textarea(attrs={'rows': 6, 'ref': 'textInput'}),
            'attachment': forms.ClearableFileInput(
                attrs={"accept": ".jpg,.jpeg,.gif,.png,.txt"}
            ),
        }

    def clean_text(self):
        value = self.cleaned_data.get("text", "").strip()

        if not value:
            raise forms.ValidationError(
                "Текст комментария обязателен."
            )

        MAX_TEXT_LENGTH = 5000
        if len(value) > MAX_TEXT_LENGTH:
            raise forms.ValidationError(
                f"Текст комментария не должен превышать {MAX_TEXT_LENGTH} символов."
            )

        # 1. Сначала проверяем HTML
        parser = CommentHTMLValidator()

        try:
            parser.feed(value)
            parser.close()
            parser.validate()
        except ValueError as error:
            raise forms.ValidationError(str(error))

        # 2. Затем очищаем HTML
        cleaned = sanitize_comment_html(value)

        # 3. Проверяем, что текст после очистки не пустой
        if not re.sub(r"<[^>]*>", "", cleaned).strip():
            raise forms.ValidationError(
                "Текст комментария не может быть пустым после удаления HTML тегов."
            )

        return cleaned


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Добавляем атрибуты для клиентской валидации
        self.fields["user_name"].widget.attrs["pattern"] = "[A-Za-z0-9]+"
        self.fields["user_name"].widget.attrs["title"] = "Только латинские буквы и цифры"
        self.fields["user_name"].widget.attrs["required"] = True
        self.fields["email"].widget.attrs["required"] = True
        self.fields["text"].widget.attrs["required"] = True

    def clean_user_name(self):
        """Валидация имени пользователя: только латинские буквы и цифры."""
        value = self.cleaned_data.get("user_name", "").strip()
        if not value:
            raise forms.ValidationError("Имя пользователя обязательно.")
        if not re.fullmatch(r"[A-Za-z0-9]+", value):
            raise forms.ValidationError("Разрешены только латинские буквы и цифры.")
        return value

    def clean_email(self):
        value = self.cleaned_data.get("email", "").strip()

        if not value:
            raise forms.ValidationError("E-mail обязателен.")

        if not re.fullmatch(
            r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
            r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+",
            value
        ):
            raise forms.ValidationError(
                "Введите корректный E-mail адрес."
            )

        return value

    def clean_home_page(self):
        """Валидация домашней страницы: формат URL."""
        value = self.cleaned_data.get("home_page", "").strip()
        if value:
            if not value.startswith(('http://', 'https://')):
                raise forms.ValidationError(
                    "Введите корректный URL (начинается с http:// или https://)"
                )
        return value


    def clean_attachment(self):
        """Валидация вложений: изображения (JPG, GIF, PNG) и TXT файлы."""
        uploaded = self.cleaned_data.get("attachment")
        if not uploaded:
            return uploaded

        # Проверяем расширение файла
        extension = uploaded.name.rsplit(".", 1)[-1].lower() if "." in uploaded.name else ""
        
        # Проверка TXT файла
        if extension == "txt":
            if uploaded.size > 100 * 1024:
                raise forms.ValidationError("TXT-файл не должен быть больше 100 КБ.")
            return uploaded

        # Проверка изображений
        if extension not in {"jpg", "jpeg", "gif", "png"}:
            raise forms.ValidationError("Допустимы только JPG, GIF, PNG или TXT.")

        MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 МБ
        if uploaded.size > MAX_IMAGE_SIZE:
            raise forms.ValidationError("Изображение слишком большое (максимум 5 МБ).")

        # Проверяем, что файл является корректным изображением
        # Проверяем, что файл является корректным изображением
        # Проверяем, что файл является корректным изображением
        try:
            image = Image.open(uploaded)
            image.verify()
            uploaded.seek(0)
            image = Image.open(uploaded)
        except Image.DecompressionBombError:
            raise forms.ValidationError(
                "Изображение слишком большое по разрешению."
            )
        except (UnidentifiedImageError, OSError):
            raise forms.ValidationError("Файл не является корректным изображением.")
        
        # Проверяем размеры и при необходимости уменьшаем
        if image.width > 320 or image.height > 240:
            image.thumbnail((320, 240), Image.Resampling.LANCZOS)

        # Сохраняем изображение в правильном формате
        output_format = "JPEG" if extension in {"jpg", "jpeg"} else extension.upper()
        if output_format == "JPEG" and image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")

        from io import BytesIO
        buffer = BytesIO()
        image.save(buffer, format=output_format)
        return ContentFile(buffer.getvalue(), name=uploaded.name)

    def save(self, commit=True):
        """Сохраняем комментарий с определением типа вложения."""
        comment = super().save(commit=False)
        attachment = self.cleaned_data.get("attachment")
        if attachment:
            comment.attachment_kind = "text" if attachment.name.lower().endswith(".txt") else "image"
        if commit:
            comment.save()
        return comment
    
    
