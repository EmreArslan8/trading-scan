#!/usr/bin/env python3
"""Masaüstü sürüm.

    pip install pywebview
    python3 desktop.py

Yerel sunucuyu boş bir portta arka planda açar, arayüzü kendi penceresinde
gösterir. pywebview kurulu değilse varsayılan tarayıcıya düşer.
Paketleme: build.py (README → Masaüstü program).
"""

import os
import socket
import threading
from http.server import ThreadingHTTPServer

os.environ.setdefault("TV_DESKTOP", "1")  # server/_gate import edilmeden önce

# Paketlenmiş programda Python'un OpenSSL'i sertifikaları derlendiği makinedeki
# yolda arar; kullanıcının bilgisayarında o yol yoktur ve HTTPS düşer.
try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
except ImportError:
    pass

from server import Handler  # noqa: E402

TITLE = "TradingView Tarayıcı"


def free_port(preferred=8777):
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]


def main():
    server = ThreadingHTTPServer(("127.0.0.1", free_port()), Handler)
    url = f"http://127.0.0.1:{server.server_address[1]}"
    threading.Thread(target=server.serve_forever, daemon=True).start()

    try:
        import webview
    except ImportError:
        webview = None

    if webview:
        webview.create_window(TITLE, url, width=1400, height=900, min_size=(900, 600))
        webview.start()
    else:
        import webbrowser
        print(f"{TITLE} çalışıyor → {url}")
        print("Kapatmak için bu pencereyi kapatın (ya da Ctrl+C).")
        webbrowser.open(url)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
    server.shutdown()


if __name__ == "__main__":
    main()
