#!/usr/bin/env python3
"""Lisans anahtarı üretir.

    python3 tools/keygen.py --init          # bir kez: gizli şifreyi oluşturur
    python3 tools/keygen.py "Ahmet Yılmaz"  # müşteriye anahtar üretir
    python3 tools/keygen.py --list          # verilen anahtarlar
    python3 tools/keygen.py --check TVS-…   # anahtar bu şifreyle mi üretilmiş

Gizli şifre .license-secret dosyasında, verilen anahtarlar licenses.csv'de
tutulur; ikisi de git'e girmez. Aynı şifre Vercel'de LICENSE_SECRET olmalı.
Şifre kaybolursa ya da değişirse eski anahtarların hepsi geçersiz olur.
"""

import csv
import secrets
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))

from _license import make_key, verify  # noqa: E402

SECRET_FILE = ROOT / ".license-secret"
LEDGER = ROOT / "licenses.csv"


def secret():
    if not SECRET_FILE.exists():
        sys.exit("Önce: python3 tools/keygen.py --init")
    return SECRET_FILE.read_text().strip().encode()


def main(args):
    if not args:
        sys.exit(__doc__)
    if args[0] == "--init":
        if SECRET_FILE.exists():
            sys.exit(f"{SECRET_FILE.name} zaten var; üzerine yazmak eski anahtarları geçersiz kılar.")
        SECRET_FILE.write_text(secrets.token_urlsafe(32) + "\n")
        SECRET_FILE.chmod(0o600)
        print(f"Oluşturuldu: {SECRET_FILE}")
        print("Bu değeri Vercel'de LICENSE_SECRET ortam değişkeni olarak ekleyin.")
    elif args[0] == "--list":
        print(LEDGER.read_text() if LEDGER.exists() else "henüz anahtar yok")
    elif args[0] == "--check":
        ok, reason = verify(args[1], secret())
        print("geçerli" if ok else f"geçersiz: {reason}")
    else:
        key = make_key(secret())
        new = not LEDGER.exists()
        with LEDGER.open("a", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            if new:
                w.writerow(["tarih", "musteri", "anahtar"])
            w.writerow([date.today().isoformat(), " ".join(args), key])
        print(key)


if __name__ == "__main__":
    main(sys.argv[1:])
