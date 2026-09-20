"""Mum verisi kaynakları: Yahoo Finance (hisse/forex) ve Binance (kripto)."""

import json
import urllib.error
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# TradingView periyot kimliği → kaynakların karşılıkları
YAHOO_INTERVAL = {"": "1d", "|1": "1m", "|5": "5m", "|15": "15m", "|60": "60m",
                  "|1W": "1wk", "|1M": "1mo"}
BINANCE_INTERVAL = {"": "1d", "|1": "1m", "|5": "5m", "|15": "15m", "|60": "1h",
                    "|240": "4h", "|1W": "1w", "|1M": "1M"}
# Yahoo'da aralık periyoda göre sınırlı. Gereğinden geniş aralık istemek
# yanıtı kat kat yavaşlatır, bu yüzden istenen mum sayısına göre seçilir:
# (en fazla kaç mum, aralık) — listedeki ilk yeterli aralık kullanılır.
YAHOO_RANGE = {
    "1m":  [(300, "1d"), (1600, "5d"), (None, "7d")],
    "5m":  [(150, "5d"), (400, "1mo"), (None, "60d")],
    "15m": [(120, "5d"), (400, "1mo"), (None, "60d")],
    "60m": [(150, "1mo"), (500, "3mo"), (1600, "1y"), (None, "2y")],
    "1d":  [(200, "1y"), (480, "2y"), (1200, "5y"), (None, "10y")],
    "1wk": [(50, "1y"), (250, "5y"), (None, "10y")],
    "1mo": [(55, "5y"), (None, "10y")],
}


def yahoo_range(interval, bars):
    for limit, rng in YAHOO_RANGE[interval]:
        if limit is None or bars <= limit:
            return rng
    return YAHOO_RANGE[interval][-1][1]
SUFFIX = {
    "turkey": ".IS", "america": "", "canada": ".TO", "japan": ".T",
    "india": ".NS", "singapore": ".SI", "hongkong": ".HK",
    "australia": ".AX", "brazil": ".SA", "germany": ".DE",
    "france": ".PA", "italy": ".MI", "spain": ".MC", "uk": ".L",
}
EXCHANGE_SUFFIX = {
    "BIST": ".IS", "TSX": ".TO", "TSXV": ".V", "TSE": ".T",
    "NSE": ".NS", "BSE": ".BO", "SGX": ".SI", "HKEX": ".HK",
    "ASX": ".AX", "BMFBOVESPA": ".SA", "XETR": ".DE",
    "EURONEXT": ".PA", "MIL": ".MI", "BME": ".MC", "LSE": ".L",
}


class FeedError(Exception):
    pass


def _get(url, timeout=15):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as exc:
        raise FeedError(f"veri kaynağı {exc.code}") from None
    except Exception as exc:
        raise FeedError(f"veri alınamadı: {type(exc).__name__}") from None


def feed_symbol(ticker, market):
    """'BIST:THYAO' → veri kaynağındaki sembol."""
    exchange = ticker.split(":", 1)[0] if ":" in ticker else ""
    plain = ticker.split(":")[-1]
    if market == "crypto":
        return plain
    if market == "forex":
        return plain + "=X"
    if market == "hongkong" and plain.isdigit():
        plain = plain.zfill(4)
    return plain + EXCHANGE_SUFFIX.get(exchange, SUFFIX.get(market, ""))


def fetch_yahoo(symbol, timeframe, bars):
    interval = YAHOO_INTERVAL.get(timeframe)
    if not interval:
        raise FeedError("bu periyot hisse verisinde yok (4 saatlik yalnızca kriptoda)")
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           f"?interval={interval}&range={yahoo_range(interval, bars)}")
    body = _get(url)
    result = (body.get("chart") or {}).get("result")
    if not result:
        raise FeedError("sembol bulunamadı")
    quote = result[0]["indicators"]["quote"][0]
    keep = [i for i, c in enumerate(quote.get("close") or []) if c is not None]
    if not keep:
        raise FeedError("mum verisi boş")
    keep = keep[-bars:]
    candles = {k: [quote[k][i] for i in keep] for k in ("open", "high", "low", "close", "volume")}
    timestamps = result[0].get("timestamp") or []
    candles["time"] = [timestamps[i] for i in keep]
    return candles


def fetch_binance(symbol, timeframe, bars):
    interval = BINANCE_INTERVAL.get(timeframe)
    if not interval:
        raise FeedError("desteklenmeyen periyot")
    url = (f"https://api.binance.com/api/v3/klines?symbol={symbol}"
           f"&interval={interval}&limit={min(bars, 1000)}")
    rows = _get(url)
    if not rows:
        raise FeedError("mum verisi boş")
    return {
        "time":   [int(r[0]) // 1000 for r in rows],
        "open":   [float(r[1]) for r in rows],
        "high":   [float(r[2]) for r in rows],
        "low":    [float(r[3]) for r in rows],
        "close":  [float(r[4]) for r in rows],
        "volume": [float(r[5]) for r in rows],
    }


def fetch_bars(ticker, market, timeframe, bars=400):
    """Bir sembolün mumlarını uygun kaynaktan getirir."""
    symbol = feed_symbol(ticker, market)
    if market == "crypto":
        return fetch_binance(symbol, timeframe, bars)
    return fetch_yahoo(symbol, timeframe, bars)
