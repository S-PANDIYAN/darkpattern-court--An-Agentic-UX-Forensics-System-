"""Thin Playwright wrapper: open pages, replay action paths, snapshot UI state, screenshot."""
from __future__ import annotations
import re
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, Page

from .. import config

SNAPSHOT_JS = (Path(__file__).parent / "snapshot.js").read_text()
MARK_ELEMENTS_JS = (Path(__file__).parent / "mark_elements.js").read_text()
TIMER_RE = re.compile(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b")
COUNTER_RE = re.compile(r"\b(\d{1,4})\s+(?:people|others|users|shoppers|customers|left|in stock|viewing)", re.I)


try:
    from playwright_stealth import Stealth
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False


class Browser:
    def __init__(self):
        self._pw = None
        self._browser = None
        self.context = None

    def __enter__(self):
        self._pw = sync_playwright().start()
        kw = {
            "headless": config.HEADLESS,
            "args": [
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-infobars",
                "--window-size=1280,800",
            ],
        }
        if config.CHROMIUM_PATH:
            kw["executable_path"] = config.CHROMIUM_PATH
        self._browser = self._pw.chromium.launch(**kw)
        return self

    def new_context(self):
        if self.context:
            try:
                self.context.close()
            except Exception:
                pass
        headers = {
            "Sec-Ch-Ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
        }
        self.context = self._browser.new_context(
            viewport=config.VIEWPORT,
            device_scale_factor=1,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            extra_http_headers=headers,
            java_script_enabled=True,
            locale="en-US",
            timezone_id="Asia/Kolkata",
            permissions=["geolocation"],
            geolocation={"latitude": 12.9716, "longitude": 77.5946},
        )
        if config.STEALTH_ENABLED and STEALTH_AVAILABLE:
            try:
                Stealth().apply_stealth_sync(self.context)
            except Exception:
                pass
        self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = window.chrome || { runtime: {} };
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition = (success) => {
                    success({ coords: { latitude: 12.9716, longitude: 77.5946, accuracy: 20 } });
                };
            }
        """)
        self.context.set_default_timeout(config.NAV_TIMEOUT_MS)
        return self.context

    def get_context(self, reuse: bool = True):
        if reuse and self.context:
            return self.context
        return self.new_context()

    def __exit__(self, *exc):
        try:
            if self.context:
                self.context.close()
            self._browser.close()
        finally:
            self._pw.stop()

    # ------------------------------------------------------------------ helpers
    def open(self, url: str, reuse_context: bool = True) -> Page:
        ctx = self.get_context(reuse=reuse_context)
        page = ctx.new_page()
        try:
            # Try the normal load first.
            resp = page.goto(url, wait_until="domcontentloaded", timeout=config.NAV_TIMEOUT_MS)
            if resp and resp.status == 429:
                time.sleep(2.5)
                try:
                    page.reload(wait_until="domcontentloaded", timeout=config.NAV_TIMEOUT_MS)
                except Exception:
                    pass
        except Exception:
            # Fall back to "commit" (fires on first byte) for heavy / bot-
            # detecting sites (Netflix, Amazon) that stall domcontentloaded.
            try:
                page.goto(url, wait_until="commit", timeout=config.NAV_TIMEOUT_MS)
            except Exception:
                pass  # Best-effort — agent will still capture whatever loaded
        settle(page)
        if config.AUTO_DISMISS_OVERLAYS and not (url.startswith("file://") or "127.0.0.1" in url or "localhost" in url):
            dismiss_initial_overlays(page)
        return page


def settle(page: Page):
    try:
        page.wait_for_load_state("networkidle", timeout=2000)
    except Exception:
        pass
    # Wait for dynamic hydration or edge challenge resolution if body is initially empty
    for _ in range(8):
        try:
            body_len = len(page.inner_text("body"))
            title = page.title()
            if body_len > 80 and "just a moment" not in title.lower():
                break
        except Exception:
            pass
        page.wait_for_timeout(400)
    # Trigger micro-scroll to force hydration of lazy-loaded SPA components
    try:
        page.evaluate("() => { if (window.innerHeight) { window.scrollBy(0, 30); window.scrollBy(0, -30); } }")
    except Exception:
        pass
    page.wait_for_timeout(config.SETTLE_MS)


def dismiss_initial_overlays(page: Page):
    """Automatically dismiss non-essential blocking modals (e.g. location popups, newsletter banners)."""
    close_selectors = [
        "button[aria-label='Close']",
        "button[aria-label='close']",
        "[aria-label='Dismiss']",
        "button.modal-close",
        "button.close-modal",
        "button.btn-close",
        ".close-button",
        "button:has-text('✕')",
        "button:has-text('×')",
        "button:has-text('Skip')",
        "button:has-text('Not now')",
        "button:has-text('Later')",
        "button:has-text('Select later')",
        "button:has-text('Confirm Location')",
        "button:has-text('Use Current Location')",
        "button:has-text('Use current location')",
        "[data-testid*='close' i]",
    ]
    for sel in close_selectors:
        try:
            loc = page.locator(sel)
            if loc.count() > 0 and loc.first.is_visible():
                loc.first.click(timeout=1000)
                page.wait_for_timeout(300)
                break
        except Exception:
            pass


def snapshot(page: Page) -> dict:
    for attempt in range(3):
        try:
            page.evaluate("window.scrollTo(0,0)")
            return page.evaluate(SNAPSHOT_JS)
        except Exception as e:
            if attempt < 2 and ("Execution context was destroyed" in str(e) or "navigation" in str(e)):
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=4000)
                except Exception:
                    pass
                time.sleep(0.5)
            else:
                page.evaluate("window.scrollTo(0,0)")
                return page.evaluate(SNAPSHOT_JS)


def apply_visual_marks(page: Page) -> int:
    """Inject Set-of-Marks visual badges on interactive elements."""
    try:
        res = page.evaluate(MARK_ELEMENTS_JS)
        return res.get("markedCount", 0) if isinstance(res, dict) else 0
    except Exception:
        return 0


def remove_visual_marks(page: Page):
    """Remove Set-of-Marks overlay so regular interaction is unaffected."""
    try:
        page.evaluate("() => { const el = document.getElementById('__dpc_som_overlay__'); if (el) el.remove(); }")
    except Exception:
        pass


def screenshot(page: Page, path: Path, with_marks: bool = False):
    if with_marks:
        apply_visual_marks(page)
        try:
            page.screenshot(path=str(path), full_page=True)
        finally:
            remove_visual_marks(page)
    else:
        page.screenshot(path=str(path), full_page=True)


def find_element(snap: dict, action: dict) -> dict | None:
    """Re-locate an element described by a recorded action in a fresh snapshot with resilient fallbacks."""
    act_text = (action.get("text") or "").strip()
    act_tag = action.get("tag", "")
    act_href = action.get("href", "")
    act_norm = re.sub(r"\s+", " ", act_text).lower()

    # 1. Exact match on tag, text and href
    for el in snap["elements"]:
        if el["tag"] == act_tag and el["text"] == act_text and el.get("href", "") == act_href:
            return el

    # 2. Exact match on text and tag
    for el in snap["elements"]:
        if el["tag"] == act_tag and el["text"] == act_text:
            return el

    # 3. Normalized whitespace and case-insensitive text match with same tag
    for el in snap["elements"]:
        el_norm = re.sub(r"\s+", " ", (el.get("text") or "").strip()).lower()
        if el["tag"] == act_tag and el_norm and el_norm == act_norm:
            return el

    # 4. Fallback on text only
    for el in snap["elements"]:
        if el["text"] == act_text:
            return el

    # 5. Substring containment match (e.g. dynamic prices or badges added to button label)
    if act_norm and len(act_norm) >= 4:
        for el in snap["elements"]:
            el_norm = re.sub(r"\s+", " ", (el.get("text") or "").strip()).lower()
            if el["tag"] == act_tag and (act_norm in el_norm or el_norm in act_norm):
                return el

    # 6. Fallback on semantic icon tags (e.g. [Cart], [Close], [Search])
    if act_norm.startswith("[") and act_norm.endswith("]"):
        for el in snap["elements"]:
            el_text = (el.get("text") or "").strip().lower()
            if el_text == act_norm:
                return el

    # 7. Fallback on href for links (exact or pathname match)
    if act_href and act_tag == "a":
        for el in snap["elements"]:
            if el["tag"] == "a" and el.get("href") == act_href:
                return el
        # Match URL path ignoring query params
        act_path = act_href.split("?")[0].split("#")[0].rstrip("/")
        if act_path and len(act_path) > 3:
            for el in snap["elements"]:
                if el["tag"] == "a" and el.get("href"):
                    el_path = el["href"].split("?")[0].split("#")[0].rstrip("/")
                    if el_path == act_path:
                        return el

    return None


def perform(page: Page, el: dict, input_val: str = ""):
    loc = page.locator(f'[data-dpc-id="{el["id"]}"]').first
    tag = (el.get("tag") or "").lower()
    el_type = (el.get("type") or "").lower()

    try:
        loc.scroll_into_view_if_needed(timeout=2500)
        # If the target is a text/search input field, fill it and press Enter
        if tag in ("input", "textarea") and el_type not in ("submit", "button", "checkbox", "radio", "hidden"):
            val = input_val or ("560001" if "location" in (el.get("text") or "").lower() else "item")
            loc.fill(val, timeout=2000)
            loc.press("Enter")
        else:
            loc.click(timeout=2000)
    except Exception:
        try:
            if tag in ("input", "textarea") and el_type not in ("submit", "button", "checkbox", "radio", "hidden"):
                loc.evaluate(f"e => {{ e.value = '{input_val or 'test'}'; e.dispatchEvent(new Event('input', {{bubbles: true}})); }}")
            else:
                loc.evaluate("e => e.click()")
        except Exception:
            pass
    settle(page)


def replay(browser: Browser, start_url: str, actions: list[dict]) -> Page | None:
    # On live HTTP/HTTPS websites, add a brief polite pause to avoid triggering anti-bot 429 rate limits
    if start_url.startswith("http"):
        time.sleep(0.8)
    page = browser.open(start_url, reuse_context=True)
    for act in actions:
        snap = snapshot(page)
        el = find_element(snap, act)
        if not el:
            # Brief retry after micro-scroll for dynamically hydrated elements
            try:
                page.evaluate("() => window.scrollBy(0, 40)")
                page.wait_for_timeout(600)
                snap = snapshot(page)
                el = find_element(snap, act)
            except Exception:
                pass
        if not el:
            try:
                page.close()
            except Exception:
                pass
            return None
        perform(page, el)
    return page


def temporal_probe(page: Page, wait_s: float = 2.0) -> dict:
    """Forensic test for fake urgency/social proof: read timers & counters, wait, reload, read again.
    A genuine deadline keeps counting down across reloads; a fake one resets or jumps."""
    def read():
        txt = page.evaluate("() => (document.body ? document.body.innerText : '')")
        timers = [int(h) * 3600 + int(m) * 60 + int(s) if s else int(h) * 60 + int(m)
                  for h, m, s in TIMER_RE.findall(txt)]
        counters = [m.group(0) for m in COUNTER_RE.finditer(txt)]
        return timers, counters
    t1, c1 = read()
    if not t1 and not c1:
        return {}
    time.sleep(wait_s)
    page.reload(wait_until="domcontentloaded")
    settle(page)
    t2, c2 = read()
    return {"timers_before": t1, "timers_after": t2, "counters_before": c1, "counters_after": c2, "elapsed_s": wait_s}
