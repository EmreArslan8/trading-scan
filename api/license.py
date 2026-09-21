"""/api/license — masaüstü lisans anahtarını doğrular.

POST {"key": "TVS-..."} → {"valid": true} ya da {"valid": false, "error": "..."}
GET → {"desktop": false}  (arayüz masaüstü sürümde olup olmadığını buradan anlar)
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _license import verify


class handler(BaseHTTPRequestHandler):
    def send_json(self, status, data):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self.send_json(200, {"desktop": False})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            key = str(json.loads(self.rfile.read(length) or b"{}").get("key", ""))
        except Exception:
            self.send_json(400, {"valid": False, "error": "istek okunamadı"})
            return
        ok, reason = verify(key)
        self.send_json(200, {"valid": True} if ok else {"valid": False, "error": reason})
