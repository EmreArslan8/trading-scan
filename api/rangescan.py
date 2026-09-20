"""POST /api/rangescan — önceki ay/çeyrek aralığına göre sembol tarar."""

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from threading import Lock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _core import MARKETS, BadRequest
from _feeds import FeedError, fetch_bars
from _gate import Blocked, check

MAX_TICKERS = 30
WORKERS = 25
PERIODS = {"month", "quarter"}
LEVELS = {"low", "mid", "high"}
CONDITIONS = {"below", "above"}
MONTHS_TR = ("", "Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara")
CACHE_TTL = 300
CACHE_MAX = 2500
_CANDLE_CACHE = {}
_CACHE_LOCK = Lock()


def _cached_bars(ticker, market):
    """Aynı sembolün mumlarını kısa süre yeniden indirme."""
    key = market, ticker
    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _CANDLE_CACHE.get(key)
        if cached and now - cached[0] < CACHE_TTL:
            return cached[1]

    # 190 işlem günü mevcut ve önceki çeyreği güvenle kapsar; Yahoo'da
    # iki yıllık yerine daha küçük bir yıllık yanıt kullanılmasını sağlar.
    candles = fetch_bars(ticker, market, "", 190)
    with _CACHE_LOCK:
        if len(_CANDLE_CACHE) >= CACHE_MAX:
            expired = [k for k, (stamp, _) in _CANDLE_CACHE.items() if now - stamp >= CACHE_TTL]
            for old in expired:
                _CANDLE_CACHE.pop(old, None)
            if len(_CANDLE_CACHE) >= CACHE_MAX:
                _CANDLE_CACHE.pop(next(iter(_CANDLE_CACHE)))
        _CANDLE_CACHE[key] = now, candles
    return candles


def _period_key(ts, period):
    date = datetime.fromtimestamp(ts, tz=timezone.utc)
    if period == "month":
        return date.year, date.month
    return date.year, ((date.month - 1) // 3) + 1


def _period_label(key, period):
    if period == "month":
        return f"{MONTHS_TR[key[1]]} {key[0]}"
    return f"Q{key[1]} {key[0]}"


def calculate_range(candles, period, level, condition):
    times = candles.get("time") or []
    closes = candles.get("close") or []
    if len(times) < 2 or not closes:
        raise FeedError("yeterli tarihsel mum yok")

    current_key = _period_key(times[-1], period)
    completed = {}
    for i, ts in enumerate(times):
        key = _period_key(ts, period)
        if key == current_key:
            continue
        bucket = completed.setdefault(key, {"high": [], "low": []})
        high, low = candles["high"][i], candles["low"][i]
        if high is not None:
            bucket["high"].append(float(high))
        if low is not None:
            bucket["low"].append(float(low))

    valid = [key for key, values in completed.items() if values["high"] and values["low"]]
    if not valid:
        raise FeedError("tamamlanmış önceki periyot yok")

    previous_key = max(valid)
    previous = completed[previous_key]
    range_high = max(previous["high"])
    range_low = min(previous["low"])
    reference = {"low": range_low, "mid": (range_high + range_low) / 2, "high": range_high}[level]
    price = float(closes[-1])
    signal = price < reference if condition == "below" else price > reference
    distance = ((price / reference) - 1) * 100 if reference else None
    return {
        "signal": signal,
        "price": price,
        "reference": reference,
        "rangeLow": range_low,
        "rangeHigh": range_high,
        "distance": distance,
        "periodLabel": _period_label(previous_key, period),
    }


def run_range_scan(req):
    market = req.get("market")
    if market not in MARKETS:
        raise BadRequest(f"bilinmeyen piyasa: {market}")
    period = req.get("period", "month")
    level = req.get("level", "low")
    condition = req.get("condition", "below")
    if period not in PERIODS or level not in LEVELS or condition not in CONDITIONS:
        raise BadRequest("geçersiz range taraması")

    tickers = req.get("tickers") or []
    if not tickers:
        raise BadRequest("sembol listesi boş")
    if len(tickers) > MAX_TICKERS:
        raise BadRequest(f"tek istekte en fazla {MAX_TICKERS} sembol")

    def one(ticker):
        row = {"ticker": ticker, "symbol": ticker.split(":")[-1]}
        try:
            candles = _cached_bars(ticker, market)
            row.update({"ok": True, **calculate_range(candles, period, level, condition)})
        except FeedError as exc:
            row.update({"ok": False, "error": str(exc)})
        except Exception as exc:
            row.update({"ok": False, "error": type(exc).__name__})
        return row

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        rows = list(pool.map(one, tickers))
    return {
        "rows": rows,
        "hits": sum(1 for row in rows if row.get("signal")),
        "failed": sum(1 for row in rows if not row.get("ok")),
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
            check(self.headers, spend=False)
            req = json.loads(self.rfile.read(length) or b"{}")
            self._send(200, run_range_scan(req))
        except Blocked as exc:
            self._send(402, {"error": str(exc), "needKey": True})
        except BadRequest as exc:
            self._send(400, {"error": str(exc)})
        except Exception as exc:
            self._send(500, {"error": f"{type(exc).__name__}: {exc}"})
