"""Tavily AI Reconnaissance & Scout Engine.

Acts as the intelligent pre-audit scout:
1. Deep-Link Target Discovery: Resolves generic homepages (e.g. netflix.com, amazon.in)
   into exact functional deep URLs (e.g. netflix.com/cancelplan) so Playwright skips
   3-5 confusing homepage navigation steps and avoids early dead-ends.
2. Policy & Fine-Print Extraction: Extracts full Terms of Service, Cancellation Policies,
   and Refund FAQs via Tavily cloud proxies without getting blocked by bot protections.
3. Legal Precedent Search: Retrieves live FTC, CCPA, and GDPR enforcement actions
   matching detected dark patterns for the Court Verdict.
"""
from __future__ import annotations
import re
from urllib.parse import urlparse
from typing import Callable

from .. import config

try:
    from tavily import TavilyClient
    TAVILY_LIB_AVAILABLE = True
except ImportError:
    TAVILY_LIB_AVAILABLE = False


_client: TavilyClient | None = None


def is_tavily_available() -> bool:
    """Check if Tavily client library and API key are available and enabled."""
    return bool(config.TAVILY_ENABLED and TAVILY_LIB_AVAILABLE and config.TAVILY_API_KEY)


def get_tavily_client() -> TavilyClient | None:
    """Cached singleton TavilyClient instance."""
    global _client
    if not is_tavily_available():
        return None
    if _client is None:
        try:
            _client = TavilyClient(api_key=config.TAVILY_API_KEY)
        except Exception as exc:
            print(f"[scout] Warning: Failed to initialize TavilyClient: {exc}")
            return None
    return _client


GOAL_SEARCH_TEMPLATES = {
    "cancel_subscription": [
        "site:{domain} cancel subscription OR manage membership OR cancel plan OR end membership",
        "site:{domain} account cancel OR membership billing settings",
    ],
    "reject_cookies": [
        "site:{domain} cookie policy OR manage cookies OR privacy preferences",
    ],
    "unsubscribe": [
        "site:{domain} unsubscribe email preferences OR opt out notifications",
    ],
    "checkout": [
        "site:{domain} cart OR store OR shop products",
    ],
    "explore": [
        "site:{domain} categories OR deals OR shop",
    ],
}


def discover_target_url(start_url: str, goal_key: str, log_fn: Callable[[str], None] = print) -> str:
    """Use Tavily Search to resolve a root homepage into a deep-link target URL for the given goal."""
    if not start_url or start_url.startswith("file://"):
        return start_url

    parsed = urlparse(start_url)
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]

    # If the user already provided an exact deep link (not just '/' or empty path), keep it
    path = (parsed.path or "").strip()
    if path and path != "/" and len(path) > 2:
        return start_url

    client = get_tavily_client()
    if not client:
        log_fn(f"[scout] Tavily not configured — starting directly at: {start_url}")
        return start_url

    queries = GOAL_SEARCH_TEMPLATES.get(goal_key, GOAL_SEARCH_TEMPLATES["explore"])
    log_fn(f"[scout] Scouting deep-link target for goal '{goal_key}' on {domain} via Tavily...")

    for template in queries:
        query = template.format(domain=domain)
        try:
            res = client.search(
                query=query,
                search_depth="basic",
                max_results=5,
                include_domains=[domain, f"www.{domain}"],
            )
            results = res.get("results", [])
            for r in results:
                cand_url = r.get("url", "")
                cand_parsed = urlparse(cand_url)
                cand_netloc = cand_parsed.netloc.lower()
                if cand_netloc.startswith("www."):
                    cand_netloc = cand_netloc[4:]

                # Ensure candidate belongs to target site and is not just the root
                if domain in cand_netloc and cand_parsed.path and cand_parsed.path != "/":
                    title = r.get("title", "")
                    log_fn(f"[scout] Found deep-link target via Tavily: {cand_url} ('{title[:60]}')")
                    return cand_url
        except Exception as exc:
            log_fn(f"[scout] Tavily search error: {exc}")
            break

    log_fn(f"[scout] No direct deep-link found via search — falling back to root: {start_url}")
    return start_url


def extract_policy_text(domain_or_url: str, log_fn: Callable[[str], None] = print) -> dict:
    """Scrape and extract clean text from Terms of Service or Cancellation policy using Tavily Extract."""
    client = get_tavily_client()
    if not client:
        return {}

    parsed = urlparse(domain_or_url)
    domain = parsed.netloc or domain_or_url
    if domain.startswith("www."):
        domain = domain[4:]

    policy_url = domain_or_url if domain_or_url.startswith("http") else f"https://{domain}"

    try:
        # First discover policy URL if a bare domain was provided
        if not parsed.path or parsed.path == "/":
            search_res = client.search(
                query=f"site:{domain} terms of service OR cancellation policy OR refund terms",
                max_results=2,
            )
            items = search_res.get("results", [])
            if items:
                policy_url = items[0]["url"]

        log_fn(f"[scout] Extracting fine-print policy from: {policy_url} via Tavily...")
        ext_res = client.extract(urls=[policy_url])
        results = ext_res.get("results", [])
        if results:
            content = results[0].get("raw_content", "") or results[0].get("content", "")
            return {
                "url": policy_url,
                "text": content[:12000],  # Truncate to relevant policy context
                "title": results[0].get("title", "Policy Document"),
            }
    except Exception as exc:
        log_fn(f"[scout] Error extracting policy via Tavily: {exc}")

    return {}


def find_legal_precedents(dark_pattern_type: str, company: str = "", log_fn: Callable[[str], None] = print) -> list[dict]:
    """Retrieve live regulatory enforcement actions (FTC, CCPA, EU) for the Court Verdict."""
    client = get_tavily_client()
    if not client:
        return []

    target = f'"{company}" ' if company else ""
    query = f'FTC OR CCPA enforcement fine penalty dark pattern {target}"{dark_pattern_type.replace("_", " ")}"'
    try:
        res = client.search(query=query, max_results=3, search_depth="basic")
        precedents = []
        for r in res.get("results", []):
            precedents.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "summary": r.get("content", "")[:300],
            })
        return precedents
    except Exception as exc:
        log_fn(f"[scout] Legal search error: {exc}")
        return []

