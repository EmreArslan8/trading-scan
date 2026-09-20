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
# Yahoo'da veri aralığı, periyoda göre sınırlı
YAHOO_RANGE = {"1m": "7d", "5m": "60d", "15m": "60d", "60m": "730d",
               "1d": "5y", "1wk": "10y", "1mo": "10y"}
SUFFIX = {"turkey": ".IS", "america": "", "germany": ".DE", "uk": ".L"}


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
    plain = ticker.split(":")[-1]
    if market == "crypto":
        return plain
    if market == "forex":
        return plain + "=X"
    return plain + SUFFIX.get(market, "")


def fetch_yahoo(symbol, timeframe, bars):
    interval = YAHOO_INTERVAL.get(timeframe)
    if not interval:
        raise FeedError("bu periyot hisse verisinde yok (4 saatlik yalnızca kriptoda)")
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           f"?interval={interval}&range={YAHOO_RANGE[interval]}")
    body = _get(url)
    result = (body.get("chart") or {}).get("result")
    if not result:
        raise FeedError("sembol bulunamadı")
    quote = result[0]["indicators"]["quote"][0]
    keep = [i for i, c in enumerate(quote.get("close") or []) if c is not None]
    if not keep:
        raise FeedError("mum verisi boş")
    keep = keep[-bars:]
    return {k: [quote[k][i] for i in keep] for k in ("open", "high", "low", "close", "volume")}


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
