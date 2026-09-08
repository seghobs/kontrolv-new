import re
from urllib.parse import urlparse


import unicodedata

USERNAME_RE = re.compile(r"^[a-zA-Z0-9._]{1,30}$")
ANDROID_ID_RE = re.compile(r"^[a-fA-F0-9]{16}$")
DEVICE_ID_RE = re.compile(r"^[a-fA-F0-9-]{8,64}$")


def normalize_username(username):
    """
    Instagram kullanıcı adını Türkçe 'I', 'İ', 'ı' karakter uyumsuzluklarından arındırır,
    küçük harfe çevirir, '@' işaretini ve baştaki/sondaki boşlukları temizler.
    """
    if not username:
        return ""
    u = str(username).strip()
    u = u.replace("İ", "i").replace("I", "i").replace("ı", "i")
    u = u.lower()
    u = unicodedata.normalize("NFKD", u)
    u = "".join(c for c in u if not unicodedata.combining(c))
    u = u.replace("ğ", "g").replace("ü", "u").replace("ş", "s").replace("ö", "o").replace("ç", "c")
    return u.lstrip("@").strip()


def is_valid_username(value):
    return bool(USERNAME_RE.fullmatch(normalize_username(value)))


def is_valid_android_id(value):
    return bool(ANDROID_ID_RE.fullmatch(str(value or "").strip()))


def is_valid_device_id(value):
    return bool(DEVICE_ID_RE.fullmatch(str(value or "").strip()))


def is_valid_post_link(value):
    raw = str(value or "").strip()
    if not raw:
        return False

    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        return False
    if not parsed.netloc:
        return False
    return True
