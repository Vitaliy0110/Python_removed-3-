import hashlib

from django import template

register = template.Library()


@register.filter
def avatar_url(email, size=44):
    """
    Возвращает URL аватарки Gravatar для указанного email.
    Если у пользователя нет аккаунта на Gravatar, сервис сам
    сгенерирует случайную "монстрик"-иконку (identicon-стиль,
    как на скриншоте) на основе хэша email.
    """
    normalized_email = (email or "").strip().lower().encode("utf-8")
    email_hash = hashlib.md5(normalized_email).hexdigest()

    return f"https://www.gravatar.com/avatar/{email_hash}?s={size}&d=identicon"
