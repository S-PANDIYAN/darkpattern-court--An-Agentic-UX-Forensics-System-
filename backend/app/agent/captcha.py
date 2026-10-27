"""Automated CAPTCHA detector and solver utilizing Kaggle GPU LLaVA-13B vision model.

Detects common bot verification challenges:
  - Amazon text captchas (amzn.to, amazon.*)
  - Common image text captchas (<img src="...captcha..."> with <input name="...captcha...">)
  - Distorted alphanumeric verification puzzles

Extracts the challenge image, queries LLaVA-13B on GPU, and automatically fills in the answer.
"""
from __future__ import annotations
import re
import time
from pathlib import Path
from playwright.sync_api import Page

from ..vision import vlm

CAPTCHA_TEXT_PATTERNS = [
    re.compile(r"type the characters you see in this image", re.I),
    re.compile(r"enter the characters.*below", re.I),
    re.compile(r"solve this puzzle.*protect your account", re.I),
    re.compile(r"security verification", re.I),
    re.compile(r"bot detection", re.I),
    re.compile(r"enter the text from the image", re.I),
    re.compile(r"verify you are a human", re.I),
]


def detect_captcha(page: Page, snap: dict | None = None) -> dict | None:
    """Check if the current page contains an active CAPTCHA challenge."""
    body_text = snap.get("text", "") if snap else ""
    if not body_text:
        try:
            body_text = page.inner_text("body", timeout=1000)
        except Exception:
            body_text = ""

    # 1. Amazon specific verification
    if "validateCaptcha" in page.url or any(p.search(body_text) for p in CAPTCHA_TEXT_PATTERNS):
        # Look for the captcha image
        img_locators = [
            page.locator("form[action*='validateCaptcha'] img"),
            page.locator("img[src*='captcha']"),
            page.locator("img[alt*='captcha']"),
            page.locator("img[id*='captcha']"),
            page.locator(".a-box img"),
        ]
        img_el = None
        for loc in img_locators:
            if loc.count() > 0 and loc.first.is_visible():
                img_el = loc.first
                break

        # Look for the captcha input box
        input_locators = [
            page.locator("input[id*='captchacharacters']"),
            page.locator("input[name*='captcha']"),
            page.locator("input[id*='captcha']"),
            page.locator("input[placeholder*='character']"),
            page.locator("input[type='text']"),
        ]
        input_el = None
        for loc in input_locators:
            if loc.count() > 0 and loc.first.is_visible():
                input_el = loc.first
                break

        # Look for submit button
        btn_locators = [
            page.locator("button[type='submit']"),
            page.locator("input[type='submit']"),
            page.locator("button:has-text('Continue shopping')"),
            page.locator("button:has-text('Submit')"),
            page.locator(".a-button-primary button"),
        ]
        btn_el = None
        for loc in btn_locators:
            if loc.count() > 0 and loc.first.is_visible():
                btn_el = loc.first
                break

        if img_el and input_el:
            return {
                "type": "image_text_captcha",
                "image_locator": img_el,
                "input_locator": input_el,
                "submit_locator": btn_el,
            }

    return None


def solve_and_submit_captcha(page: Page, captcha_info: dict, temp_dir: Path, log_fn=print) -> bool:
    """Crop the captcha, query LLaVA-13B, type answer, and submit."""
    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
        img_path = temp_dir / "captcha_crop.png"
        log_fn("[CAPTCHA] CAPTCHA detected. Capturing image for GPU LLaVA-13B analysis...")

        # Screenshot the image element directly
        captcha_info["image_locator"].screenshot(path=str(img_path))

        # Ask LLaVA-13B on Kaggle GPU to solve it
        log_fn(f"[CAPTCHA] Sending {img_path.name} to GPU LLaVA-13B solver...")
        solution = vlm.solve_captcha_image(img_path)
        log_fn(f"[CAPTCHA] LLaVA-13B returned answer: '{solution}'")

        if not solution:
            log_fn("[CAPTCHA] Model could not decipher text.")
            return False

        # Type solution into input box
        inp = captcha_info["input_locator"]
        inp.fill("")
        inp.type(solution, delay=60)
        time.sleep(0.5)

        # Submit
        btn = captcha_info.get("submit_locator")
        if btn and btn.is_visible():
            btn.click()
        else:
            inp.press("Enter")

        time.sleep(3.0)
        log_fn("[CAPTCHA] Submitted solution. Waiting for page reload...")
        return True
    except Exception as exc:
        log_fn(f"[CAPTCHA] Error during solving attempt: {exc}")
        return False
