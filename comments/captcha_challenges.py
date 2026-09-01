import random
import string

from captcha.conf import settings as captcha_settings


def alnum_challenge():
    # Генерирует CAPTCHA из латинских букв и цифр
    chars = string.ascii_lowercase + string.digits
    length = captcha_settings.CAPTCHA_LENGTH
    value = "".join(random.choice(chars) for _ in range(length))
    return value.upper(), value