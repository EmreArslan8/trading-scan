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
    "netherlands": ".AS", "belgium": ".BR", "portugal": ".LS",
    "ireland": ".IR", "switzerland": ".SW", "austria": ".VI",
    "denmark": ".CO", "sweden": ".ST", "norway": ".OL", "finland": ".HE",
    "poland": ".WA", "greece": ".AT", "newzealand": ".NZ",
    "korea": ".KS", "taiwan": ".TW", "indonesia": ".JK",
    "thailand": ".BK", "israel": ".TA", "china": ".SS",
    "chile": ".SN", "argentina": ".BA",
}
# Borsa kodu, piyasa varsayılanını ezer. EURONEXT bilerek yok: Amsterdam,
# Brüksel, Lizbon, Dublin ve Paris aynı kod altında toplanır ama Yahoo'da
# ayrı ekler alır, o yüzden kararı piyasa verir.
EXCHANGE_SUFFIX = {
    "BIST": ".IS", "TSX": ".TO", "TSXV": ".V", "TSE": ".T",
    "NSE": ".NS", "BSE": ".BO", "SGX": ".SI", "HKEX": ".HK",
    "ASX": ".AX", "BMFBOVESPA": ".SA", "XETR": ".DE",
    "CSE": ".CN", "NEO": ".NE",
    "MIL": ".MI", "BME": ".MC", "LSE": ".L",
    "SIX": ".SW", "VIE": ".VI", "OMXCOP": ".CO", "OMXSTO": ".ST",
    "OSL": ".OL", "OMXHEX": ".HE", "GPW": ".WA", "ATHEX": ".AT",
    "NZX": ".NZ", "KRX": ".KS", "TWSE": ".TW", "TPEX": ".TWO",
    "IDX": ".JK", "SET": ".BK", "TASE": ".TA",
    "SSE": ".SS", "SZSE": ".SZ", "BCS": ".SN", "BCBA": ".BA",
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


def _plain_and_suffix(ticker, market):
    """Sembolü kaynak yazımına çevirir ve ekini ayrı döner."""
    exchange = ticker.split(":", 1)[0] if ":" in ticker else ""
    plain = ticker.split(":")[-1]
    # Hisse sınıfı ayıracı: TradingView "_" (ABD'de "."), Yahoo "-" kullanır.
    # ERIC_B -> ERIC-B, NOVO_B -> NOVO-B, BRK.B -> BRK-B
    plain = plain.replace("_", "-")
    if market == "america":
        plain = plain.replace(".", "-")
    if market == "hongkong" and plain.isdigit():
        plain = plain.zfill(4)
    return plain, EXCHANGE_SUFFIX.get(exchange, SUFFIX.get(market, ""))


def feed_symbol(ticker, market):
    """'BIST:THYAO' → veri kaynağındaki sembol."""
    plain = ticker.split(":")[-1]
    if market == "crypto":
        return plain
    if market == "forex":
        return plain + "=X"
    base, suffix = _plain_and_suffix(ticker, market)
    return base + suffix


def feed_symbols(ticker, market):
    """Denenecek kaynak sembolleri, en olasıdan başlayarak."""
    if market in ("crypto", "forex"):
        return [feed_symbol(ticker, market)]

    base, suffix = _plain_and_suffix(ticker, market)
    bases = [base]
    if "." in base:
        head, _, tail = base.rpartition(".")
        # TSX:RCI.B gibi hisse sınıfları kaynakta tire ile yazılır (RCI-B),
        # BCBA:METR.CI gibi takas sınıfı ekleri ise hiç yer almaz (METR).
        if head and tail:
            bases.append(f"{head}-{tail}")
        if head:
            bases.append(head)

    suffixes = [suffix] + [s for s in ALT_SUFFIX.get(market, ()) if s != suffix]
    return [b + s for b in bases for s in suffixes]


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


# Tek borsa kodunun Yahoo'da birden çok eke karşılık geldiği piyasalar:
# KRX hem KOSPI (.KS) hem KOSDAQ (.KQ) demek, sembolden hangisi olduğu
# anlaşılmıyor. Sembol bulunamazsa sıradaki ek denenir.
ALT_SUFFIX = {
    "korea": (".KS", ".KQ"),
    "taiwan": (".TW", ".TWO"),
    "china": (".SS", ".SZ"),
    "india": (".NS", ".BO"),
    "canada": (".TO", ".V"),
}

# Yalnızca "bu sembol burada yok" anlamına gelen hatalarda yedek ek denenir;
# hız sınırı ya da ağ hatasında denemeyi tekrarlamak kaynağı boşuna yorar.
NOT_FOUND = ("sembol bulunamadı", "mum verisi boş", "veri kaynağı 404")



def fetch_bars(ticker, market, timeframe, bars=400):
    """Bir sembolün mumlarını uygun kaynaktan getirir."""
    if market == "crypto":
        return fetch_binance(feed_symbol(ticker, market), timeframe, bars)

    last = None
    for symbol in feed_symbols(ticker, market):
        try:
            return fetch_yahoo(symbol, timeframe, bars)
        except FeedError as exc:
            last = exc
            if not any(text in str(exc) for text in NOT_FOUND):
                raise
    raise last
