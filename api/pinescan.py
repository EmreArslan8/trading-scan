"""POST /api/pinescan — verilen semboller üzerinde özel indikatör ifadesi çalıştırır.

Girdi:  {"tickers": [...], "market": "turkey", "timeframe": "", "expr": "...", "bars": 400}
Çıktı:  her sembol için sinyal durumu ve son değerler.
"""

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _core import MARKETS, TIMEFRAMES, BadRequest
from _feeds import FeedError, fetch_bars
from _pine import PineError, compile_expr, evaluate
from _series import Series, barssince

MAX_TICKERS = 30          # tek istekte; arayüz uzun listeyi parçalara böler
MAX_BARS = 1000
WORKERS = 25          # parça başına tek turda bitecek kadar


def run_pine_scan(req):
    market = req.get("market")
    if market not in MARKETS:
        raise BadRequest(f"bilinmeyen piyasa: {market}")

    timeframe = req.get("timeframe", "")
    if timeframe not in TIMEFRAMES:
        raise BadRequest(f"bilinmeyen periyot: {timeframe}")

    tickers = req.get("tickers") or []
    if not tickers:
        raise BadRequest("sembol listesi boş")
    if len(tickers) > MAX_TICKERS:
        raise BadRequest(f"tek istekte en fazla {MAX_TICKERS} sembol")

    bars = min(int(req.get("bars") or 400), MAX_BARS)
    tree = compile_expr(req.get("expr") or "")

    def one(ticker):
        row = {"ticker": ticker, "symbol": ticker.split(":")[-1]}
        try:
            candles = fetch_bars(ticker, market, timeframe, bars)
            result = evaluate(tree, candles)
            since = barssince(result).last
            row.update({
                "ok": True,
                "signal": bool(result.last),
                "value": None if result.last is None else round(result.last, 6),
                "close": Series(candles["close"]).last,
                "bars": len(candles["close"]),
                "sinceBars": None if since is None else int(since),
            })
        except (FeedError, PineError) as exc:
            row.update({"ok": False, "error": str(exc)})
        except Exception as exc:
            row.update({"ok": False, "error": f"{type(exc).__name__}"})
        return row

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        rows = list(pool.map(one, tickers))

    return {
        "rows": rows,
        "hits": sum(1 for r in rows if r.get("signal")),
        "failed": sum(1 for r in rows if not r.get("ok")),
    }


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
            self._send(200, run_pine_scan(json.loads(self.rfile.read(length) or b"{}")))
        except (BadRequest, PineError) as exc:
            self._send(400, {"error": str(exc)})
        except Exception as exc:
            self._send(500, {"error": f"{type(exc).__name__}: {exc}"})
