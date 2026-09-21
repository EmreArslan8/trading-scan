"""Masaüstü lisans anahtarları.

Anahtar = rastgele kimlik + LICENSE_SECRET ile HMAC imzası, base32 yazılır:
    TVS-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX
Sır yalnızca sunucuda (Vercel ortam değişkeni) ve anahtar üreten makinede
durur; program imzayı kendisi doğrulamaz, siteye sorar. İptal edilen
anahtarlar REVOKED_KEYS ortam değişkenine virgülle yazılır.

Program tarafı (DESKTOP): son başarılı kontrol ~/.tvtarayici/license.json
dosyasında tutulur. Günde bir kez yeniden sorulur; siteye ulaşılamazsa
GRACE süresi boyunca çalışmaya devam eder.
"""

import base64
import hashlib
import hmac
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

PREFIX = "TVS"
SECRET = os.environ.get("LICENSE_SECRET", "").encode()
LICENSE_URL = os.environ.get("TV_LICENSE_URL", "https://trading-scan.vercel.app/api/license")
STATE = Path.home() / ".tvtarayici" / "license.json"
RECHECK = 24 * 3600
GRACE = 7 * 24 * 3600


def normalize(key):
    raw = re.sub(r"[^A-Z0-9]", "", (key or "").upper())
    return raw[len(PREFIX):] if raw.startswith(PREFIX) else raw


def _sig(ident, secret):
    return hmac.new(secret, ident, hashlib.sha256).digest()[:7]


REVOKED = {normalize(k) for k in os.environ.get("REVOKED_KEYS", "").split(",") if k.strip()}


def make_key(secret=SECRET):
    ident = os.urandom(8)
    body = base64.b32encode(ident + _sig(ident, secret)).decode()  # 24 karakter
    return "-".join([PREFIX] + [body[i:i + 4] for i in range(0, 24, 4)])


def verify(key, secret=SECRET):
    """Sunucu tarafı doğrulama. Döner: (geçerli_mi, sebep)."""
    if not secret:
        return False, "sunucuda lisans ayarı yok"
    body = normalize(key)
    try:
        raw = base64.b32decode(body)
    except Exception:
        return False, "anahtar biçimi hatalı"
    if len(raw) != 15 or not hmac.compare_digest(raw[8:], _sig(raw[:8], secret)):
        return False, "anahtar geçersiz"
    if body in REVOKED:
        return False, "bu anahtar iptal edilmiş"
    return True, ""


# ── program tarafı ─────────────────────────────────────────────

def _ask_server(key):
    """Siteye sorar. Ağ hatasında OSError yükseltir."""
    req = urllib.request.Request(
        LICENSE_URL, data=json.dumps({"key": key}).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "TVTarayici"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        if exc.code >= 500:
            raise OSError(f"lisans sunucusu {exc.code}") from exc
        data = json.load(exc)
    return bool(data.get("valid")), data.get("error") or ""


def _load():
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}


def _save(state):
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(state))
    except OSError:
        pass


def activate(key):
    """Anahtarı siteye doğrulatıp kaydeder. Döner: (başarılı_mı, mesaj)."""
    try:
        ok, reason = _ask_server(key)
    except OSError as exc:
        why = getattr(exc, "reason", exc)
        return False, f"lisans sunucusuna ulaşılamadı ({why}), internet bağlantısını kontrol edin"
    if ok:
        _save({"key": key.strip(), "checked": int(time.time())})
    return ok, reason


def licensed():
    """Bu bilgisayarda geçerli lisans var mı (gerekirse siteye yeniden sorar)."""
    state = _load()
    key, checked = state.get("key"), state.get("checked", 0)
    if not key:
        return False
    age = time.time() - checked
    if age < RECHECK:
        return True
    try:
        ok, _ = _ask_server(key)
    except OSError:
        return age < GRACE  # çevrimdışı tolerans
    if ok:
        _save({"key": key, "checked": int(time.time())})
    else:
        _save({})  # iptal edildi ya da geçersiz
    return ok
