#!/usr/bin/env python3
"""Yerel geliştirme sunucusu.

    python3 server.py        # http://127.0.0.1:8777

Vercel'de aynı işi api/scan.py ve api/catalog.py fonksiyonları görür;
tarama mantığı tek yerde, api/_core.py içindedir.
"""

import json
import sys
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / "api"))

from _core import CATALOG, BadRequest, run_scan  # noqa: E402
from _gate import DESKTOP, Blocked, check  # noqa: E402
from _license import activate, licensed, verify  # noqa: E402
from _pine import PineError  # noqa: E402
from pinescan import run_pine_scan  # noqa: E402
from rangescan import run_range_scan  # noqa: E402

PUBLIC = (BASE / "public").resolve()
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".js": "text/javascript; charset=utf-8", ".json": "application/json; charset=utf-8",
         ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon"}


class Handler(BaseHTTPRequestHandler):
    server_version = "TVScreener/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def send_json(self, status, data, cookie=None):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path.startswith("/api/catalog"):
            self.send_json(200, CATALOG)
            return
        if self.path == "/api/license":
            self.send_json(200, {"desktop": DESKTOP, "licensed": DESKTOP and licensed()})
            return

        name = "index.html" if self.path in ("/", "") else self.path.lstrip("/").split("?")[0]
        path = (PUBLIC / name).resolve()
        if not path.is_file() or PUBLIC not in path.parents:
            self.send_error(404)
            return

        raw = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", TYPES.get(path.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        if self.path == "/api/reset":
            self.send_json(
                200, {"ok": True},
                "tvdemo=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax",
            )
            return
        if self.path == "/api/license":
            try:
                length = int(self.headers.get("Content-Length") or 0)
                key = str(json.loads(self.rfile.read(length) or b"{}").get("key", ""))
            except Exception:
                self.send_json(400, {"valid": False, "error": "istek okunamadı"})
                return
            ok, reason = activate(key) if DESKTOP else verify(key)
            self.send_json(200, {"valid": True} if ok else {"valid": False, "error": reason})
            return
        routes = {"/api/scan": run_scan, "/api/pinescan": run_pine_scan,
                  "/api/rangescan": run_range_scan}
        action = routes.get(self.path)
        if action is None:
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(length) or b"{}")
            spend = self.path == "/api/scan"
            cookie, left = check(self.headers, spend=spend)
            result = action(req)
            if spend:
                result["scansLeft"] = left
            self.send_json(200, result, cookie)
        except Blocked as exc:
            self.send_json(402, {"error": str(exc), "needKey": True})
        except (BadRequest, PineError) as exc:
            self.send_json(400, {"error": str(exc)})
        except urllib.error.HTTPError as exc:
            self.send_json(502, {"error": f"TradingView {exc.code}: {exc.reason}"})
        except urllib.error.URLError as exc:
            self.send_json(502, {"error": f"bağlanılamadı: {exc.reason}"})
        except Exception as exc:  # son çare
            self.send_json(500, {"error": f"{type(exc).__name__}: {exc}"})


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8777
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"TradingView tarayıcı hazır → http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nkapatılıyor")
        server.server_close()


if __name__ == "__main__":
    main()
