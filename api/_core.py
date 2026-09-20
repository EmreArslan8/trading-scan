"""Tarama çekirdeği. Hem yerel sunucu hem Vercel fonksiyonları bunu kullanır."""

import json
import re
import urllib.request
from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parent / "fields.json"
CATALOG = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

FIELDS = {f["id"]: f for f in CATALOG["fields"]}
OPS = {o["id"]: o for o in CATALOG["operators"]}
MARKETS = {m["id"] for m in CATALOG["markets"]}
TIMEFRAMES = {t["id"] for t in CATALOG["timeframes"]}

SCANNER = "https://scanner.tradingview.com/{market}/scan"
MAX_ROWS = 500
MAX_ALL_ROWS = 2000
PAGE_SIZE = 500


class BadRequest(Exception):
    pass


def col(field_id, timeframe):
    """Alan kimliğini, seçili zaman dilimine göre TradingView kolon adına çevirir."""
    if field_id not in FIELDS:
        raise BadRequest(f"bilinmeyen alan: {field_id}")
    if timeframe and FIELDS[field_id]["tf"]:
        return field_id + timeframe
    return field_id


def as_number(raw):
    """'1.5M', '2,5', '1e6' gibi girdileri sayıya çevirir."""
    if isinstance(raw, (int, float)):
        return raw
    text = str(raw).strip().replace(" ", "").replace(",", ".")
    if not text:
        raise BadRequest("boş değer")
    mult = {"k": 1e3, "m": 1e6, "b": 1e9}.get(text[-1].lower())
    if mult:
        text = text[:-1]
    else:
        mult = 1
    if not re.fullmatch(r"-?\d*\.?\d+(e-?\d+)?", text, re.I):
        raise BadRequest(f"sayı okunamadı: {raw}")
    return float(text) * mult


def build_filter(rule, timeframe):
    op = rule.get("op")
    if op not in OPS:
        raise BadRequest(f"bilinmeyen operatör: {op}")
    left = col(rule.get("field"), timeframe)

    if rule.get("isColumn"):
        right = col(rule.get("value"), timeframe)
    elif OPS[op]["arity"] == 2:
        right = [as_number(rule.get("value")), as_number(rule.get("value2"))]
    else:
        right = as_number(rule.get("value"))

    return {"left": left, "operation": op, "right": right}


def build_payload(req):
    market = req.get("market")
    if market not in MARKETS:
        raise BadRequest(f"bilinmeyen piyasa: {market}")

    timeframe = req.get("timeframe", "")
    if timeframe not in TIMEFRAMES:
        raise BadRequest(f"bilinmeyen zaman dilimi: {timeframe}")

    rules = req.get("filters") or []
    if not rules:
        raise BadRequest("en az bir kriter gerekir")

    chosen = req.get("columns") or ["close", "change", "volume"]
    columns = ["name", "description"] + [col(c, timeframe) for c in chosen]

    sort = req.get("sort") or {}
    sort_by = col(sort.get("by", "volume"), timeframe)
    order = "asc" if sort.get("order") == "asc" else "desc"

    all_rows = bool(req.get("all"))
    limit = min(int(req.get("limit") or (MAX_ALL_ROWS if all_rows else 100)),
                MAX_ALL_ROWS if all_rows else MAX_ROWS)

    return {
        "filter": [build_filter(r, timeframe) for r in rules],
        "options": {"lang": "tr"},
        "markets": [market],
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": columns,
        "sort": {"sortBy": sort_by, "sortOrder": order},
        "range": [0, min(limit, PAGE_SIZE)],
    }, chosen, market, limit, all_rows


def run_scan(req):
    payload, chosen, market, limit, all_rows = build_payload(req)

    def fetch_page(start, end):
        page = dict(payload)
        page["range"] = [start, end]
        request = urllib.request.Request(
            SCANNER.format(market=market),
            data=json.dumps(page).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                "Origin": "https://www.tradingview.com",
                "Referer": "https://www.tradingview.com/",
            },
        )
        with urllib.request.urlopen(request, timeout=25) as resp:
            return json.load(resp)

    body = fetch_page(0, min(limit, PAGE_SIZE))
    items = list(body.get("data", []))
    total = body.get("totalCount", len(items))
    if all_rows:
        while len(items) < min(total, limit):
            start = len(items)
            page = fetch_page(start, min(start + PAGE_SIZE, limit))
            fresh = page.get("data", [])
            if not fresh:
                break
            items.extend(fresh)

    rows = []
    for item in items[:limit]:
        values = item.get("d", [])
        rows.append({
            "ticker": item.get("s", ""),
            "symbol": values[0] if values else "",
            "name": values[1] if len(values) > 1 else "",
            "values": values[2:],
        })

    return {
        "total": total,
        "columns": chosen,
        "rows": rows,
        "query": {**payload, "range": [0, limit]},
    }
