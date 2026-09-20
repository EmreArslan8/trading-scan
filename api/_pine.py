"""Pine benzeri ifadeleri güvenle çalıştıran değerlendirici.

`eval` kullanılmaz: ifade AST'ye çevrilir, yalnızca izin verilen düğüm türleri
ve isimler işlenir. Döngü, atama, öznitelik erişimi, içe aktarma yoktur.
"""

import ast
import math

from _series import (
    NaN, Series, barssince, change, cross, crossover, crossunder, ema, falling,
    highest, lowest, nz, rising, rma, rsi, s_abs, s_and, s_max, s_min, s_not,
    s_or, s_sum, sma, stdev, series, wma,
)

MAX_LENGTH = 2000          # ifade uzunluğu
MAX_NODES = 400            # ifade karmaşıklığı


class PineError(Exception):
    pass


ALLOWED_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.Call,
    ast.Name, ast.Load, ast.Constant, ast.Subscript, ast.Index if hasattr(ast, "Index") else ast.Load,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow, ast.USub, ast.UAdd,
    ast.And, ast.Or, ast.Not, ast.Gt, ast.GtE, ast.Lt, ast.LtE, ast.Eq, ast.NotEq,
)


def build_env(bars):
    """Mum verisinden ifade ortamını kurar."""
    o = Series(bars["open"])
    h = Series(bars["high"])
    l = Series(bars["low"])
    c = Series(bars["close"])
    v = Series(bars["volume"])

    def tr():
        prev = c.shift(1)
        return s_max(h - l, s_max(s_abs(h - prev), s_abs(l - prev)))

    def atr(length=14):
        return rma(tr(), length)

    def macd_line(fast=12, slow=26, src=None):
        src = c if src is None else src
        return ema(src, fast) - ema(src, slow)

    def macd_signal(fast=12, slow=26, signal=9, src=None):
        return ema(macd_line(fast, slow, src), signal)

    def macd_hist(fast=12, slow=26, signal=9, src=None):
        return macd_line(fast, slow, src) - macd_signal(fast, slow, signal, src)

    def stoch_k(length=14, smooth=1):
        hh, ll = highest(h, length), lowest(l, length)
        raw = (c - ll) / (hh - ll) * 100
        return sma(raw, smooth) if smooth > 1 else raw

    def stoch_d(length=14, smooth=1, dlen=3):
        return sma(stoch_k(length, smooth), dlen)

    def bb_basis(length=20, src=None):
        return sma(c if src is None else src, length)

    def bb_upper(length=20, mult=2, src=None):
        return bb_basis(length, src) + stdev(c if src is None else src, length) * mult

    def bb_lower(length=20, mult=2, src=None):
        return bb_basis(length, src) - stdev(c if src is None else src, length) * mult

    def dmi(length=14):
        up = h - h.shift(1)
        down = l.shift(1) - l
        plus_raw, minus_raw = [], []
        for u, d in zip(up.v, down.v):
            if math.isnan(u) or math.isnan(d):
                plus_raw.append(NaN); minus_raw.append(NaN); continue
            plus_raw.append(u if (u > d and u > 0) else 0.0)
            minus_raw.append(d if (d > u and d > 0) else 0.0)
        atr_ = rma(tr(), length)
        plus = rma(Series(plus_raw), length) / atr_ * 100
        minus = rma(Series(minus_raw), length) / atr_ * 100
        return plus, minus

    def di_plus(length=14):
        return dmi(length)[0]

    def di_minus(length=14):
        return dmi(length)[1]

    def adx(length=14):
        plus, minus = dmi(length)
        dx = s_abs(plus - minus) / (plus + minus) * 100
        return rma(dx, length)

    def vwap():
        tp = (h + l + c) / 3
        num = den = 0.0
        out = []
        for price, vol in zip(tp.v, v.v):
            if math.isnan(price) or math.isnan(vol):
                out.append(NaN); continue
            num += price * vol
            den += vol
            out.append(num / den if den else NaN)
        return Series(out)

    env = {
        # kaynaklar
        "open": o, "high": h, "low": l, "close": c, "volume": v,
        "hl2": (h + l) / 2, "hlc3": (h + l + c) / 3, "ohlc4": (o + h + l + c) / 4,
        # ortalamalar
        "sma": sma, "ema": ema, "rma": rma, "wma": wma, "vwap": vwap,
        # osilatörler
        "rsi": rsi, "stoch": stoch_k, "stoch_k": stoch_k, "stoch_d": stoch_d,
        "macd": macd_line, "macd_signal": macd_signal, "macd_hist": macd_hist,
        "atr": atr, "tr": tr, "adx": adx, "di_plus": di_plus, "di_minus": di_minus,
        "bb_upper": bb_upper, "bb_lower": bb_lower, "bb_basis": bb_basis, "stdev": stdev,
        # yardımcılar
        "highest": highest, "lowest": lowest, "change": change, "crossover": crossover,
        "crossunder": crossunder, "cross": cross, "rising": rising, "falling": falling,
        "barssince": barssince, "nz": nz, "abs": s_abs, "sum": s_sum,
        "max": s_max, "min": s_min,
    }
    return env


def known_names():
    """İfadede geçebilecek tüm isimler (kaynaklar + fonksiyonlar)."""
    empty = {k: [] for k in ("open", "high", "low", "close", "volume")}
    return set(build_env(empty))


def _check(node, depth=0):
    if depth > 40:
        raise PineError("ifade fazla iç içe")
    if not isinstance(node, ALLOWED_NODES):
        raise PineError(f"ifadede izin verilmeyen yapı: {type(node).__name__}")
    for child in ast.iter_child_nodes(node):
        _check(child, depth + 1)


def compile_expr(text):
    """İfadeyi doğrular ve AST'sini döndürür."""
    if not text or not text.strip():
        raise PineError("ifade boş")
    if len(text) > MAX_LENGTH:
        raise PineError(f"ifade {MAX_LENGTH} karakteri aşıyor")

    # Pine sözdiziminden Python'a küçük çeviriler
    cleaned = text.strip()
    for a, b in (("ta.", ""), ("math.", ""), ("and not", "and not"), ("//", "#")):
        cleaned = cleaned.replace(a, b)
    cleaned = " ".join(line.split("#")[0] for line in cleaned.splitlines())

    try:
        tree = ast.parse(cleaned, mode="eval")
    except SyntaxError as exc:
        raise PineError(f"sözdizimi hatası: {exc.msg}") from None

    if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
        raise PineError("ifade fazla karmaşık")
    _check(tree)

    allowed = known_names()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in allowed:
            raise PineError(f"tanımsız isim: {node.id}")
    return tree


def _eval(node, env):
    if isinstance(node, ast.Expression):
        return _eval(node.body, env)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return 1.0 if node.value else 0.0
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise PineError("yalnızca sayı sabitleri kullanılabilir")

    if isinstance(node, ast.Name):
        if node.id not in env:
            raise PineError(f"tanımsız isim: {node.id}")
        return env[node.id]

    if isinstance(node, ast.BinOp):
        left, right = _eval(node.left, env), _eval(node.right, env)
        left = series(left) if not isinstance(left, Series) else left
        op = type(node.op)
        if op is ast.Add: return left + right
        if op is ast.Sub: return left - right
        if op is ast.Mult: return left * right
        if op is ast.Div: return left / right
        if op is ast.Mod: return left % right
        if op is ast.Pow: return left ** right
        raise PineError("desteklenmeyen işlem")

    if isinstance(node, ast.UnaryOp):
        val = _eval(node.operand, env)
        if isinstance(node.op, ast.USub): return -series(val)
        if isinstance(node.op, ast.UAdd): return series(val)
        if isinstance(node.op, ast.Not): return s_not(val)
        raise PineError("desteklenmeyen tekli işlem")

    if isinstance(node, ast.BoolOp):
        values = [_eval(v, env) for v in node.values]
        combine = s_and if isinstance(node.op, ast.And) else s_or
        result = values[0]
        for nxt in values[1:]:
            result = combine(result, nxt)
        return result

    if isinstance(node, ast.Compare):
        if len(node.ops) > 3:
            raise PineError("zincirleme karşılaştırma fazla uzun")
        left = _eval(node.left, env)
        result = None
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval(comparator, env)
            lhs = series(left) if not isinstance(left, Series) else left
            kind = type(op)
            if kind is ast.Gt: cmp_ = lhs > right
            elif kind is ast.GtE: cmp_ = lhs >= right
            elif kind is ast.Lt: cmp_ = lhs < right
            elif kind is ast.LtE: cmp_ = lhs <= right
            elif kind is ast.Eq: cmp_ = lhs == right
            elif kind is ast.NotEq: cmp_ = lhs != right
            else: raise PineError("desteklenmeyen karşılaştırma")
            result = cmp_ if result is None else s_and(result, cmp_)
            left = right
        return result

    if isinstance(node, ast.Subscript):
        target = _eval(node.value, env)
        index = node.slice.value if hasattr(node.slice, "value") and isinstance(node.slice, ast.Index) else node.slice
        offset = _eval(index, env)
        offset = offset.last if isinstance(offset, Series) else offset
        if offset is None:
            raise PineError("geçersiz gecikme")
        return series(target).shift(int(offset))

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise PineError("yalnızca doğrudan fonksiyon çağrısı yapılabilir")
        fn = env.get(node.func.id)
        if not callable(fn):
            raise PineError(f"bilinmeyen fonksiyon: {node.func.id}")
        if node.keywords:
            raise PineError("adlandırılmış argüman desteklenmiyor")
        args = [_eval(a, env) for a in node.args]
        try:
            return fn(*args)
        except PineError:
            raise
        except TypeError as exc:
            raise PineError(f"{node.func.id}() argümanları hatalı: {exc}") from None
        except Exception as exc:
            raise PineError(f"{node.func.id}() çalışmadı: {exc}") from None

    raise PineError(f"ifadede izin verilmeyen yapı: {type(node).__name__}")


def evaluate(tree, bars):
    """İfadeyi bir sembolün mumları üzerinde çalıştırır."""
    env = build_env(bars)
    result = _eval(tree, env)
    return series(result) if not isinstance(result, Series) else result
