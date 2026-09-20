"""GET /api/catalog — piyasa, periyot, operatör ve alan tanımları."""

import json
from http.server import BaseHTTPRequestHandler

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _core import CATALOG


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        raw = json.dumps(CATALOG, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "public, max-age=300")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
