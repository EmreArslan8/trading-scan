#!/usr/bin/env python3
"""Masaüstü programı paketler (PyInstaller).

    pip install pywebview pyinstaller
    python3 build.py

Çıktı: dist/TVTarayici.app (macOS) · dist/TVTarayici.exe (Windows).
Her işletim sistemi kendi programını derler; Windows .exe'si Mac'te çıkmaz,
bunun için .github/workflows/desktop.yml kullanılır.
"""

import os
import sys

import PyInstaller.__main__

SEP = os.pathsep  # --add-data ayırıcısı: Windows ';', diğerleri ':'

PyInstaller.__main__.run([
    "desktop.py",
    "--name=TVTarayici",
    "--windowed",
    "--onefile" if sys.platform == "win32" else "--onedir",
    "--noconfirm",
    "--clean",
    "--paths=api",
    f"--add-data=public{SEP}public",
    f"--add-data=api/fields.json{SEP}.",
    *[f"--hidden-import={m}" for m in
      ("_core", "_gate", "_pine", "_series", "_feeds", "pinescan", "rangescan")],
])
