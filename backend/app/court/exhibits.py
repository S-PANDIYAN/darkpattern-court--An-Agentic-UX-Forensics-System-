"""Evidence card imagery: crops the full-page screenshot around a finding and draws the
forensic bounding box, producing an 'Exhibit' image for the court record."""
from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

RED = (220, 38, 38)


def _font(size):
    for f in ["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf"]:
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_exhibit(screenshot: Path, bbox: dict | None, out: Path, label: str) -> bool:
    if not screenshot.exists():
        return False
    im = Image.open(screenshot).convert("RGB")
    if bbox and bbox.get("w", 0) > 0:
        x, y, w, h = bbox["x"], bbox["y"], bbox["w"], bbox["h"]
        pad = 60
        crop = (max(0, x - pad * 3), max(0, y - pad), min(im.width, x + w + pad * 3), min(im.height, y + h + pad))
        d = ImageDraw.Draw(im)
        for i in range(4):
            d.rectangle([x - 4 - i, y - 4 - i, x + w + 4 + i, y + h + 4 + i], outline=RED)
        im = im.crop(crop)
    else:
        im = im.crop((0, 0, im.width, min(im.height, 520)))
    # caption strip
    strip_h = 34
    canvas = Image.new("RGB", (im.width, im.height + strip_h), (17, 24, 39))
    canvas.paste(im, (0, strip_h))
    ImageDraw.Draw(canvas).text((10, 8), label[:110], fill=(255, 255, 255), font=_font(16))
    if canvas.width > 1100:
        canvas = canvas.resize((1100, int(canvas.height * 1100 / canvas.width)))
    canvas.save(out, "PNG", optimize=True)
    return True
