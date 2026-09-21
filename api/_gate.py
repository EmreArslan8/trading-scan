"""Demo kullanım sınırı.

Sunucu tarafında kalıcı depo yok; sayaç, HMAC ile imzalanmış bir çerezde
taşınır. Kullanıcı sayacı kurcalayamaz (imza tutmaz), ama çerezi silerek
hakkını tazeleyebilir. Yani bu bir sürtünme katmanıdır, kimlik doğrulama
değildir. Gerçek kilit için ACCESS_ONLY=1 ile anahtarsız erişim kapatılır.
"""

import hashlib
import hmac
import os
import time

COOKIE = "tvdemo"
TTL = 7 * 24 * 3600

FREE_SCANS = int(os.environ.get("FREE_SCANS", "3"))
ACCESS_KEYS = {k.strip() for k in os.environ.get("ACCESS_KEYS", "").split(",") if k.strip()}
ACCESS_ONLY = os.environ.get("ACCESS_ONLY", "") == "1"
UNLIMITED = os.environ.get("TV_DESKTOP", "") == "1"  # masaüstü sürüm: sınır yok
SECRET = os.environ.get("DEMO_SECRET", "degistirilmemis-varsayilan-anahtar").encode()


class Blocked(Exception):
    """Hak bitti ya da anahtar gerekiyor."""


def _sign(payload):
    return hmac.new(SECRET, payload.encode(), hashlib.sha256).hexdigest()[:24]


def _pack(used, started):
    payload = f"{used}.{started}"
    return f"{payload}.{_sign(payload)}"


def _unpack(raw):
    try:
        used, started, sig = raw.split(".")
        if not hmac.compare_digest(sig, _sign(f"{used}.{started}")):
            return 0, int(time.time())
        if time.time() - int(started) > TTL:
            return 0, int(time.time())
        return int(used), int(started)
    except Exception:
        return 0, int(time.time())


def _cookie_value(cookie_header):
    for part in (cookie_header or "").split(";"):
        name, _, value = part.strip().partition("=")
        if name == COOKIE:
            return value
    return ""


def supplied_key(headers):
    return (headers.get("X-Access-Key") or "").strip()


def has_key(headers):
    """İstekte geçerli erişim anahtarı var mı."""
    return bool(ACCESS_KEYS) and supplied_key(headers) in ACCESS_KEYS


def check(headers, spend=True):
    """Kullanım hakkını denetler.

    Döner: (set_cookie_or_None, kalan_hak). Hak bittiyse Blocked yükseltir.
    """
    if UNLIMITED or has_key(headers):
        return None, None  # masaüstü ya da anahtarlı kullanım sınırsız

    if supplied_key(headers):
        raise Blocked("erişim anahtarı geçersiz")

    if ACCESS_ONLY:
        raise Blocked("bu demo erişim anahtarı ile kullanılıyor")

    used, started = _unpack(_cookie_value(headers.get("Cookie")))
    if used >= FREE_SCANS:
        raise Blocked(
            f"deneme hakkınız doldu ({FREE_SCANS} tarama). "
            "Devam etmek için erişim anahtarı girin."
        )

    if not spend:
        return None, FREE_SCANS - used

    used += 1
    cookie = (f"{COOKIE}={_pack(used, started)}; Path=/; Max-Age={TTL}; "
              "HttpOnly; SameSite=Lax")
    return cookie, FREE_SCANS - used
