"""Optional multimodal LLM integration using the official OpenAI Python SDK.

Supports any OpenAI-compatible endpoint:
  - OpenAI (gpt-4o, gpt-4o-mini)
  - Ollama / LLaVA running locally or on Kaggle via Cloudflare tunnel
  - OpenRouter, Azure OpenAI, Groq, LM Studio …

Configure via .env:
  LLM_API_KEY=ollama            # any placeholder string for Ollama; real key for OpenAI
  LLM_BASE_URL=https://your-cloudflare-tunnel.trycloudflare.com/v1
  LLM_MODEL=llava:7b            # or gpt-4o-mini, llava:13b, etc.

Two uses:
  * analyse_screenshot – vision model acts as a second expert witness, reports dark
    patterns it sees in the rendered screenshot (catches purely visual tricks).
  * rerank_thoughts    – LLM value function for the Tree-of-Thought search.
"""
from __future__ import annotations
import base64
import io
import json

from openai import OpenAI, OpenAIError

from .. import config
from ..models import Finding
from ..taxonomy import PATTERNS

SYSTEM = (
    "You are a UX forensics expert. Identify manipulative design (dark patterns) in UI screenshots. "
    "Only report what is clearly visible. Answer with strict JSON."
)

# ---------------------------------------------------------------------------
# Shared SDK client — created once, reused for every call.
# ---------------------------------------------------------------------------
_client: OpenAI | None = None
_llm_reachable: bool | None = None


def is_llm_available() -> bool:
    """Fast probe to verify if the configured LLM endpoint is alive."""
    global _llm_reachable
    if not config.LLM_ENABLED:
        return False
    if _llm_reachable is not None:
        return _llm_reachable
    try:
        client = _get_client()
        client.models.list(timeout=3.0)
        _llm_reachable = True
        return True
    except Exception as exc:
        print(f"[vlm] LLM endpoint unreachable ({exc}). Running offline deterministic detectors.")
        _llm_reachable = False
        return False


def _get_client() -> OpenAI:
    """Return a cached OpenAI SDK client pointed at the configured endpoint."""
    global _client
    if _client is None:
        url = (config.LLM_BASE_URL or "").strip().rstrip("/")
        if url and not url.endswith("/v1"):
            url = f"{url}/v1"
        _client = OpenAI(
            api_key=config.LLM_API_KEY or "ollama",
            base_url=url,
            timeout=6.0,
        )
    return _client


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _chat(messages: list[dict], max_tokens: int = 700) -> str:
    """Send a chat completion request using the OpenAI SDK. Returns the text content."""
    client = _get_client()
    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=messages,
        temperature=0,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
        timeout=8.0,
    )
    return response.choices[0].message.content


def _img_b64(path, max_w: int = 1024, max_h: int = 2400) -> str:
    """Resize screenshot and return as a base64-encoded JPEG string."""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    im = im.crop((0, 0, im.width, min(im.height, max_h * im.width // max_w)))
    im.thumbnail((max_w, max_h))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=70)
    return base64.b64encode(buf.getvalue()).decode()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyse_screenshot(image_path, ctx) -> list[Finding]:
    """Ask the vision model to inspect a screenshot for dark patterns.

    Returns a list of Finding objects (empty list if LLM is disabled or fails).
    Works with any vision-capable model: GPT-4o, LLaVA 7B/13B, etc.
    """
    if not is_llm_available():
        return []

    keys = ", ".join(PATTERNS)
    prompt = (
        f"Pattern keys you may use: {keys}.\n"
        f'Return {{"findings": [{{"pattern": "<key>", "evidence": "<short visual quote or description>", '
        f'"confidence": 0.0..1.0}}]}}.\n'
        f"Return an empty findings list if the page looks fair."
    )

    try:
        content = _chat(
            messages=[
                {"role": "system", "content": SYSTEM},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:image/jpeg;base64," + _img_b64(image_path)
                            },
                        },
                    ],
                },
            ]
        )
        data = json.loads(content)
    except OpenAIError as exc:
        print(f"[vlm] OpenAI SDK error during analyse_screenshot: {exc}")
        return []
    except Exception as exc:
        print(f"[vlm] analyse_screenshot failed: {exc}")
        return []

    out = []
    for f in data.get("findings", [])[:6]:
        if f.get("pattern") in PATTERNS:
            out.append(
                Finding(
                    pattern=f["pattern"],
                    description="Reported by the vision model (LLaVA expert witness).",
                    confidence=round(float(f.get("confidence", 0.5)) * 0.8, 2),
                    severity=0.5,
                    evidence=[str(f.get("evidence", ""))[:200]],
                    source="vlm",
                    node_id=ctx.get("node_id"),
                    step=ctx.get("step"),
                    url=ctx.get("url"),
                )
            )
    return out


def rerank_thoughts(goal_label: str, snap: dict, cands: list[dict]) -> list[dict]:
    """LLM value function: rate each candidate action for progress towards the goal (0–10).

    Falls back gracefully if the model is unavailable — returns cands unchanged.
    """
    if not is_llm_available() or not cands:
        return cands

    listing = "\n".join(
        f"{i}. [{c['action']['tag']}] {c['action']['text'][:80]}"
        for i, c in enumerate(cands)
    )
    prompt = (
        f"A user wants to: {goal_label}.\n"
        f"Page title: {snap['title']}.\n"
        f"Visible text (truncated): {snap['text'][:1500]}\n"
        f"Candidate actions:\n{listing}\n"
        f'Return {{"ratings": [{{"i": <index>, "score": 0..10, "why": "<short reason>"}}]}}.'
    )

    try:
        data = json.loads(
            _chat(
                messages=[
                    {"role": "system", "content": "You evaluate UI navigation steps. Strict JSON only."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=400,
            )
        )
        for r in data.get("ratings", []):
            idx = int(r["i"])
            if 0 <= idx < len(cands):
                cands[idx]["score"] = round(0.5 * cands[idx]["score"] + 0.5 * float(r["score"]), 2)
                cands[idx]["rationale"] += f" | LLM: {r.get('why', '')[:80]}"
    except OpenAIError as exc:
        print(f"[vlm] OpenAI SDK error during rerank_thoughts: {exc}")
    except Exception as exc:
        print(f"[vlm] rerank_thoughts failed: {exc}")

    return sorted(cands, key=lambda c: -c["score"])


def solve_captcha_image(image_path) -> str:
    """Use LLaVA-13B on Kaggle GPU to transcribe a distorted CAPTCHA image."""
    if not is_llm_available():
        return ""
    prompt = (
        "This image contains a distorted CAPTCHA verification challenge. "
        "Carefully read and transcribe the exact letters and numbers shown. "
        "Return strict JSON: {\"captcha\": \"<letters_or_numbers>\"}."
    )
    try:
        content = _chat(
            messages=[
                {"role": "system", "content": "You are a specialized OCR tool for reading verification codes. Output strict JSON."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:image/jpeg;base64," + _img_b64(str(image_path))
                            },
                        },
                    ],
                },
            ],
            max_tokens=60,
        )
        data = json.loads(content)
        return str(data.get("captcha", "")).strip()
    except Exception as exc:
        print(f"[vlm] CAPTCHA solver error: {exc}")
        return ""


def decide_som_action(goal_label: str, snap: dict, marked_image_path, cands: list[dict]) -> dict | None:
    """Visually grounded decision making using Set-of-Marks annotated screenshot.

    LLaVA-13B observes the numbered boxes on the screenshot and identifies
    which numbered badge represents the true next step for the user,
    bypassing deceptive decoy buttons and dark pattern nudges.
    """
    if not is_llm_available() or not cands:
        return None

    elements_summary = "\n".join(
        f"Badge [{c['action'].get('id', i)}]: tag=<{c['action']['tag']}> text=\"{c['action']['text'][:60]}\""
        for i, c in enumerate(cands[:15])
    )
    prompt = (
        f"The user wants to accomplish: '{goal_label}'.\n"
        f"In the screenshot, interactive UI elements are tagged with numbered colored badges [0, 1, 2, ...].\n"
        f"Candidates:\n{elements_summary}\n\n"
        f"Which badge number should the user interact with to make fair progress towards their goal, "
        f"avoiding deceptive popups, fake offers, or manipulative traps?\n"
        f"Return strict JSON: {{\"selected_badge\": <number_or_id>, \"reason\": \"<brief reason>\"}}."
    )

    try:
        content = _chat(
            messages=[
                {"role": "system", "content": "You are an autonomous web user agent analyzing a Set-of-Marks screenshot. Strict JSON."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:image/jpeg;base64," + _img_b64(str(marked_image_path))
                            },
                        },
                    ],
                },
            ],
            max_tokens=200,
        )
        data = json.loads(content)
        chosen_id = str(data.get("selected_badge", ""))
        for c in cands:
            if str(c["action"].get("id", "")) == chosen_id:
                c["score"] += 15.0  # Visual AI boost
                c["rationale"] += f" | Visual SoM: {data.get('reason', '')[:80]}"
                return c
    except Exception as exc:
        print(f"[vlm] Visual SoM decision failed: {exc}")
    return None

