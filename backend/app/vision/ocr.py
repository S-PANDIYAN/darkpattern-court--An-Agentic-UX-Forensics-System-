"""Screenshot + OCR pipeline. Finds text that is rendered visually (e.g. baked into images or
canvas) but absent from the DOM — a common way to hide claims from text-based scanners."""
from __future__ import annotations
import re
from .. import config

try:
    import pytesseract
    from PIL import Image
    pytesseract.get_tesseract_version()
    OCR_AVAILABLE = config.OCR_ENABLED
except Exception:  # binary or package missing
    OCR_AVAILABLE = False


def ocr_lines(image_path) -> list[str]:
    if not OCR_AVAILABLE:
        return []
    img = Image.open(image_path)
    if img.height > 6000:
        img = img.crop((0, 0, img.width, 6000))
    txt = pytesseract.image_to_string(img.convert("L"))
    return [re.sub(r"\s+", " ", l).strip() for l in txt.splitlines() if len(l.strip()) > 3]


def ocr_only_lines(image_path, dom_text: str) -> list[str]:
    dom = re.sub(r"\W+", " ", dom_text.lower())
    out = []
    for line in ocr_lines(image_path):
        words = [w for w in re.sub(r"\W+", " ", line.lower()).split() if len(w) > 3]
        if words and sum(w in dom for w in words) / len(words) < 0.5:
            out.append(line)
    return out
