"""Seri aritmetiği ve indikatörler — saf Python, bağımlılık yok.

Pine'daki seri mantığını taklit eder: her değer bir mumun karşılığıdır,
işlemler eleman elemandır, veri yetmediğinde sonuç None olur.
"""

import math

NaN = float("nan")


def _f(x):
    """None ve nan'ı tek bir gösterime indirger."""
    if x is None:
        return NaN
    return float(x)


def _ok(x):
    return x is not None and not math.isnan(x)


class Series:
    __slots__ = ("v",)

    def __init__(self, values):
        self.v = [_f(x) for x in values]

    def __len__(self):
        return len(self.v)

    def __iter__(self):
        return iter(self.v)

    @property
    def last(self):
        for x in reversed(self.v):
            if not math.isnan(x):
                return x
        return None

    def shift(self, n):
        """close[1] karşılığı: seriyi n mum geciktirir."""
        n = int(n)
        if n <= 0:
            return Series(self.v)
        return Series([NaN] * n + self.v[:-n])

    def __getitem__(self, n):
        return self.shift(n)

    # ── aritmetik ────────────────────────────────────────────────
    def _pair(self, other, fn):
        if isinstance(other, Series):
            n = max(len(self), len(other))
            a, b = self._pad(n), other._pad(n)
            return Series([fn(x, y) for x, y in zip(a, b)])
        o = _f(other)
        return Series([fn(x, o) for x in self.v])

    def _pad(self, n):
        return [NaN] * (n - len(self)) + self.v

    @staticmethod
    def _guard(fn):
        def wrapped(x, y):
            if math.isnan(x) or math.isnan(y):
                return NaN
            try:
                return fn(x, y)
            except ZeroDivisionError:
                return NaN
        return wrapped

    def __add__(s, o):  return s._pair(o, Series._guard(lambda a, b: a + b))
    def __radd__(s, o): return s._pair(o, Series._guard(lambda a, b: b + a))
    def __sub__(s, o):  return s._pair(o, Series._guard(lambda a, b: a - b))
    def __rsub__(s, o): return s._pair(o, Series._guard(lambda a, b: b - a))
    def __mul__(s, o):  return s._pair(o, Series._guard(lambda a, b: a * b))
    def __rmul__(s, o): return s._pair(o, Series._guard(lambda a, b: b * a))
    def __truediv__(s, o):  return s._pair(o, Series._guard(lambda a, b: a / b))
    def __rtruediv__(s, o): return s._pair(o, Series._guard(lambda a, b: b / a))
    def __mod__(s, o):  return s._pair(o, Series._guard(lambda a, b: a % b))
    def __pow__(s, o):  return s._pair(o, Series._guard(lambda a, b: a ** b))
    def __neg__(s):     return Series([-x for x in s.v])

    # ── karşılaştırma: bool serisi döner ─────────────────────────
    def _cmp(self, other, fn):
        res = self._pair(other, lambda a, b: NaN if (math.isnan(a) or math.isnan(b)) else (1.0 if fn(a, b) else 0.0))
        return res

    def __gt__(s, o): return s._cmp(o, lambda a, b: a > b)
    def __ge__(s, o): return s._cmp(o, lambda a, b: a >= b)
    def __lt__(s, o): return s._cmp(o, lambda a, b: a < b)
    def __le__(s, o): return s._cmp(o, lambda a, b: a <= b)
    def __eq__(s, o): return s._cmp(o, lambda a, b: a == b)
    def __ne__(s, o): return s._cmp(o, lambda a, b: a != b)

    def __repr__(self):
        tail = ", ".join("na" if math.isnan(x) else f"{x:.4g}" for x in self.v[-3:])
        return f"Series(len={len(self)}, …{tail})"


def series(x, n=None):
    """Sayıyı seriye yükseltir; seriyi olduğu gibi geçirir."""
    if isinstance(x, Series):
        return x
    return Series([_f(x)] * (n or 1))


def as_bool(x):
    """İfadenin sonucunu son mumdaki doğruluk değerine indirger."""
    if isinstance(x, Series):
        val = x.last
        return bool(val) if _ok(val) else False
    return bool(x)


# ── mantık (Pine'da and/or eleman elemandır) ─────────────────────
def s_and(a, b):
    a, b = series(a), series(b)
    return a._pair(b, lambda x, y: NaN if (math.isnan(x) or math.isnan(y)) else float(bool(x) and bool(y)))


def s_or(a, b):
    a, b = series(a), series(b)
    return a._pair(b, lambda x, y: NaN if (math.isnan(x) or math.isnan(y)) else float(bool(x) or bool(y)))


def s_not(a):
    a = series(a)
    return Series([NaN if math.isnan(x) else float(not bool(x)) for x in a.v])


# ── indikatörler ─────────────────────────────────────────────────
def sma(src, length):
    src, length = series(src), int(length)
    out, total, window = [], 0.0, []
    for x in src.v:
        window.append(x)
        if math.isnan(x):
            out.append(NaN)
            if len(window) > length:
                window.pop(0)
            continue
        if len(window) > length:
            window.pop(0)
        valid = [w for w in window if not math.isnan(w)]
        out.append(sum(valid) / length if len(valid) == length else NaN)
    return Series(out)


def ema(src, length):
    src, length = series(src), int(length)
    k = 2.0 / (length + 1)
    out, prev, seed = [], NaN, []
    for x in src.v:
        if math.isnan(x):
            out.append(prev)
            continue
        if math.isnan(prev):
            seed.append(x)
            if len(seed) < length:
                out.append(NaN)
                continue
            prev = sum(seed) / length
        else:
            prev = x * k + prev * (1 - k)
        out.append(prev)
    return Series(out)


def rma(src, length):
    """Wilder yumuşatması — RSI, ATR, ADX bunu kullanır."""
    src, length = series(src), int(length)
    a = 1.0 / length
    out, prev, seed = [], NaN, []
    for x in src.v:
        if math.isnan(x):
            out.append(prev)
            continue
        if math.isnan(prev):
            seed.append(x)
            if len(seed) < length:
                out.append(NaN)
                continue
            prev = sum(seed) / length
        else:
            prev = x * a + prev * (1 - a)
        out.append(prev)
    return Series(out)


def wma(src, length):
    src, length = series(src), int(length)
    weights = list(range(1, length + 1))
    denom = sum(weights)
    out = []
    for i in range(len(src)):
        window = src.v[max(0, i - length + 1): i + 1]
        if len(window) < length or any(math.isnan(w) for w in window):
            out.append(NaN)
        else:
            out.append(sum(w * k for w, k in zip(window, weights)) / denom)
    return Series(out)


def change(src, length=1):
    src = series(src)
    return src - src.shift(int(length))


def rsi(src, length=14):
    src = series(src)
    diff = change(src)
    gain = Series([NaN if math.isnan(x) else max(x, 0.0) for x in diff.v])
    loss = Series([NaN if math.isnan(x) else max(-x, 0.0) for x in diff.v])
    avg_gain, avg_loss = rma(gain, length), rma(loss, length)
    out = []
    for g, l in zip(avg_gain.v, avg_loss.v):
        if math.isnan(g) or math.isnan(l):
            out.append(NaN)
        elif l == 0:
            out.append(100.0)
        else:
            out.append(100.0 - 100.0 / (1.0 + g / l))
    return Series(out)


def stdev(src, length):
    src, length = series(src), int(length)
    out = []
    for i in range(len(src)):
        window = src.v[max(0, i - length + 1): i + 1]
        if len(window) < length or any(math.isnan(w) for w in window):
            out.append(NaN)
            continue
        mean = sum(window) / length
        out.append(math.sqrt(sum((w - mean) ** 2 for w in window) / length))
    return Series(out)


def highest(src, length):
    src, length = series(src), int(length)
    out = []
    for i in range(len(src)):
        window = [w for w in src.v[max(0, i - length + 1): i + 1] if not math.isnan(w)]
        out.append(max(window) if len(window) == length else NaN)
    return Series(out)


def lowest(src, length):
    src, length = series(src), int(length)
    out = []
    for i in range(len(src)):
        window = [w for w in src.v[max(0, i - length + 1): i + 1] if not math.isnan(w)]
        out.append(min(window) if len(window) == length else NaN)
    return Series(out)


def crossover(a, b):
    a, b = series(a), series(b)
    now, prev = a - b, (a - b).shift(1)
    out = []
    for n, p in zip(now.v, prev.v):
        out.append(NaN if (math.isnan(n) or math.isnan(p)) else float(p <= 0 < n))
    return Series(out)


def crossunder(a, b):
    return crossover(b, a)


def cross(a, b):
    return s_or(crossover(a, b), crossunder(a, b))


def rising(src, length):
    src, length = series(src), int(length)
    out = []
    for i in range(len(src)):
        window = src.v[max(0, i - length): i + 1]
        if len(window) < length + 1 or any(math.isnan(w) for w in window):
            out.append(NaN)
        else:
            out.append(float(all(b > a for a, b in zip(window, window[1:]))))
    return Series(out)


def falling(src, length):
    src, length = series(src), int(length)
    out = []
    for i in range(len(src)):
        window = src.v[max(0, i - length): i + 1]
        if len(window) < length + 1 or any(math.isnan(w) for w in window):
            out.append(NaN)
        else:
            out.append(float(all(b < a for a, b in zip(window, window[1:]))))
    return Series(out)


def barssince(cond):
    cond = series(cond)
    out, count = [], NaN
    for x in cond.v:
        if not math.isnan(x) and x:
            count = 0.0
        elif not math.isnan(count):
            count += 1
        out.append(count)
    return Series(out)


def nz(src, replacement=0):
    src = series(src)
    return Series([replacement if math.isnan(x) else x for x in src.v])


def s_abs(src):
    return Series([NaN if math.isnan(x) else abs(x) for x in series(src).v])


def s_sum(src, length):
    src, length = series(src), int(length)
    out = []
    for i in range(len(src)):
        window = src.v[max(0, i - length + 1): i + 1]
        out.append(sum(window) if len(window) == length and not any(math.isnan(w) for w in window) else NaN)
    return Series(out)


def s_max(a, b):
    return series(a)._pair(series(b), lambda x, y: NaN if (math.isnan(x) or math.isnan(y)) else max(x, y))


def s_min(a, b):
    return series(a)._pair(series(b), lambda x, y: NaN if (math.isnan(x) or math.isnan(y)) else min(x, y))
