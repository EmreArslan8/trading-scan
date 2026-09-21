#!/usr/bin/env python3
"""Program ikonunu üretir: assets/icon.png, icon.ico, icon.icns.

    pip install pillow
    python3 tools/make_icon.py

Tasarım sitenin favicon'uyla aynıdır (public/index.html): 32×32 ızgarada
koyu yuvarlak kare ve amber çizgi M7 22 l6-7 4 3 8-10, kalınlık 3.
"""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
BG = (10, 12, 16, 255)
AMBER = (255, 176, 32, 255)
LINE = [(7, 22), (13, 15), (17, 18), (25, 8)]
WIDTH = 3


def _offset(points, d):
    """Çizgiyi d kadar yana kaydırır; köşeler sivri (SVG miter) kalır."""
    segs = []
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        dx, dy = x2 - x1, y2 - y1
        n = (dx * dx + dy * dy) ** 0.5
        nx, ny = -dy / n * d, dx / n * d
        segs.append(((x1 + nx, y1 + ny), (x2 + nx, y2 + ny)))
    out = [segs[0][0]]
    for (a1, a2), (b1, b2) in zip(segs, segs[1:]):
        # iki kaydırılmış doğrunun kesişimi
        d1 = (a2[0] - a1[0], a2[1] - a1[1])
        d2 = (b2[0] - b1[0], b2[1] - b1[1])
        den = d1[0] * d2[1] - d1[1] * d2[0]
        t = ((b1[0] - a1[0]) * d2[1] - (b1[1] - a1[1]) * d2[0]) / den
        out.append((a1[0] + d1[0] * t, a1[1] + d1[1] * t))
    out.append(segs[-1][1])
    return out


def render(size, inset):
    """inset: kenarda bırakılan boşluk oranı (macOS ikon ızgarası için)."""
    ss = 4
    S = size * ss
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = S * inset
    k = (S - 2 * pad) / 32
    d.rounded_rectangle([pad, pad, S - pad, S - pad], 6 * k, fill=BG)
    pts = [(pad + x * k, pad + y * k) for x, y in LINE]
    half = WIDTH / 2 * k
    d.polygon(_offset(pts, half) + _offset(pts, -half)[::-1], fill=AMBER)
    return img.resize((size, size), Image.LANCZOS)


def main():
    OUT.mkdir(exist_ok=True)
    mac = render(1024, 100 / 1024)  # macOS: 824 px alan, gölge payı
    mac.save(OUT / "icon.png")
    mac.save(OUT / "icon.icns")
    win = render(256, 0.02)
    win.save(OUT / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("assets/icon.png · icon.ico · icon.icns")


if __name__ == "__main__":
    main()
