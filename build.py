#!/usr/bin/env python3
"""Masaüstü programı paketler (PyInstaller).

    pip install pywebview pyinstaller
    python3 build.py

Çıktı: dist/TradingViewTarayici.app (macOS) · dist/TradingViewTarayici.exe (Windows).
Her işletim sistemi kendi programını derler; Windows .exe'si Mac'te çıkmaz,
bunun için .github/workflows/desktop.yml kullanılır.
"""

import os
import sys

import PyInstaller.__main__

SEP = os.pathsep  # --add-data ayırıcısı: Windows ';', diğerleri ':'

PyInstaller.__main__.run([
    "desktop.py",
    "--name=TradingViewTarayici",
    "--icon=assets/" + ("icon.ico" if sys.platform == "win32" else "icon.icns"),
    "--osx-bundle-identifier=com.emrearslan.tradingviewtarayici",
    "--windowed",
    "--onefile" if sys.platform == "win32" else "--onedir",
    "--noconfirm",
    "--clean",
    "--paths=api",
    f"--add-data=public{SEP}public",
    f"--add-data=api/fields.json{SEP}.",
    *[f"--hidden-import={m}" for m in
      ("certifi", "_core", "_gate", "_license", "_pine", "_series", "_feeds", "pinescan", "rangescan")],
])
