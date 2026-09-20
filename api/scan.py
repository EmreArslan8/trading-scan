"""POST /api/scan — Vercel Python fonksiyonu."""

import json
import urllib.error
from http.server import BaseHTTPRequestHandler

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _core import BadRequest, run_scan


class handler(BaseHTTPRequestHandler):
    def _send(self, status, data):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(length) or b"{}")
            self._send(200, run_scan(req))
        except BadRequest as exc:
            self._send(400, {"error": str(exc)})
        except urllib.error.HTTPError as exc:
            self._send(502, {"error": f"TradingView {exc.code}: {exc.reason}"})
        except urllib.error.URLError as exc:
            self._send(502, {"error": f"bağlanılamadı: {exc.reason}"})
        except Exception as exc:
            self._send(500, {"error": f"{type(exc).__name__}: {exc}"})

    def do_GET(self):
        self._send(405, {"error": "POST kullanın"})
