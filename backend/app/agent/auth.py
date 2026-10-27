"""Human-in-the-loop authentication and login-wall detector.

Detects when a website requires real user credentials:
  - Password inputs (<input type="password">)
  - Sign-in buttons & forms ("Sign in", "Log in", "Sign in to continue")
  - Two-factor authentication (2FA), OTP, or identity confirmation prompts

When an authentication gate is encountered, the agent can pause, notify the user,
or wait for the user to authenticate in the open browser window, then automatically resume the audit!
"""
from __future__ import annotations
import time
from playwright.sync_api import Page
from .. import config

LOGIN_KEYWORDS = [
    "sign in", "log in", "login", "signin",
    "enter your password", "password", "two-factor",
    "verification code", "one-time password", "otp",
    "confirm your account"
]


def detect_login_gate(page: Page, snap: dict | None = None) -> dict | None:
    """Check if the current page requires user authentication."""
    # 1. Check for password input
    pwd_loc = page.locator("input[type='password']")
    has_pwd = False
    try:
        has_pwd = pwd_loc.count() > 0 and pwd_loc.first.is_visible()
    except Exception:
        has_pwd = False

    # 2. Check title / text for login cues
    title = (page.title() or "").lower()
    url = page.url.lower()

    is_auth_url = any(k in url for k in ["/login", "/signin", "/auth", "accounts.google", "amazon.in/ap/signin"])
    is_auth_title = any(k in title for k in ["sign in", "log in", "login"])

    if has_pwd or (is_auth_url and is_auth_title):
        # Look for username/email field
        user_loc = page.locator("input[type='email'], input[name*='user'], input[name*='email'], input[id*='email'], input[id*='user'], input[type='text']").first
        submit_loc = page.locator("button[type='submit'], input[type='submit'], button:has-text('Sign in'), button:has-text('Log in')").first

        return {
            "type": "login_required",
            "url": page.url,
            "title": page.title(),
            "has_password": has_pwd,
            "username_locator": user_loc if user_loc.count() > 0 else None,
            "password_locator": pwd_loc.first if has_pwd else None,
            "submit_locator": submit_loc if submit_loc.count() > 0 else None,
        }

    return None


def wait_for_user_login(page: Page, login_info: dict, timeout_s: int = 60, log_fn=print) -> bool:
    """Prompt the user and wait for authentication to complete in the browser window."""
    if config.HEADLESS:
        log_fn("[AUTH REQUIRED] Website presented a login wall, but browser is in HEADLESS mode.")
        log_fn("  >> To authenticate interactively, restart with DPC_HEADLESS=0 in .env.")
        log_fn("  >> Proceeding with current unauthenticated page state.")
        return False

    log_fn("\n" + "=" * 65)
    log_fn("[AUTH REQUIRED] The website presented a Login Wall:")
    log_fn(f"  URL: {login_info['url']}")
    log_fn(f"  Title: {login_info['title']}")
    log_fn("  >> Please log in or complete verification in the browser window.")
    log_fn(f"  >> Waiting up to {timeout_s} seconds for session to authenticate...")
    log_fn("=" * 65 + "\n")

    start = time.time()
    initial_url = page.url

    while time.time() - start < timeout_s:
        # Check if URL changed away from login or password field is gone
        try:
            pwd_count = page.locator("input[type='password']").count()
            if pwd_count == 0 and page.url != initial_url:
                log_fn("[AUTH SUCCESS] Login detected! Resuming automated dark-pattern audit.")
                time.sleep(2)
                return True
        except Exception:
            pass
        time.sleep(2)

    log_fn("[AUTH TIMEOUT] Login window timed out. Continuing audit with current state.")
    return False
