import re

PRICE_RE = re.compile(r"(?:₹|rs\.?|inr|\$|€|£|usd|eur)\s?(\d[\d,]*(?:\.\d{1,2})?)", re.I)


def parse_rgb(c):
    if not c:
        return None
    if isinstance(c, (list, tuple)):
        return list(c)[:3]
    m = re.match(r"rgba?\(([^)]+)\)", c)
    if not m:
        return None
    return [float(x) for x in m.group(1).split(",")[:3]]


def _lum(rgb):
    def ch(v):
        v = v / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg, bg) -> float:
    """WCAG 2.x contrast ratio between two rgb colours (1..21)."""
    fg, bg = parse_rgb(fg), parse_rgb(bg)
    if not fg or not bg:
        return 21.0
    l1, l2 = sorted([_lum(fg), _lum(bg)], reverse=True)
    return round((l1 + 0.05) / (l2 + 0.05), 2)


def saturation(rgb) -> float:
    rgb = parse_rgb(rgb)
    if not rgb:
        return 0.0
    mx, mn = max(rgb) / 255, min(rgb) / 255
    return 0.0 if mx == 0 else (mx - mn) / mx


def prices(text: str) -> list[float]:
    out = []
    for m in PRICE_RE.finditer(text or ""):
        try:
            out.append(float(m.group(1).replace(",", "")))
        except ValueError:
            pass
    return out


def norm(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "")).strip()


def short(t: str, n: int = 140) -> str:
    t = norm(t)
    return t if len(t) <= n else t[: n - 1] + "…"
