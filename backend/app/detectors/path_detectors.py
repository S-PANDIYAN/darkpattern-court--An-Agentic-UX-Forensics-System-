"""Detectors that reason over a whole decision path (sequence of page states)."""
from __future__ import annotations
import re
from ..models import Finding
from ..utils import prices, short

FEE_RX = re.compile(
    r"((?:service|convenience|handling|processing|booking|platform|packaging|restaurant packaging|surge|rain|small order|delivery partner|delivery|admin\w*|resort)\s+(?:fee|charge)s?)"
    r"[^\n₹$€£a-z0-9]{0,30}"
    r"((?:₹|rs\.?|\$|€|£|inr|usd)\s?\d[\d,]*(?:\.\d{1,2})?)",
    re.I
)
TOTAL_RX = re.compile(
    r"(?:grand\s+)?total[^\n₹$€£a-z0-9]{0,30}"
    r"((?:₹|rs\.?|\$|€|£|inr|usd)\s?\d[\d,]*(?:\.\d{1,2})?)",
    re.I
)
RETENTION_RX = re.compile(r"before you go|are you sure|wait!?|special offer|\d+\s?% off|discount|we'?ll miss you|reconsider|lose (all|your)|stay with us", re.I)


def _f(pattern, desc, conf, sev, ev, node, bbox=None):
    return Finding(pattern=pattern, description=desc, confidence=round(min(conf, .99), 2), severity=sev, evidence=ev,
                   source="path", node_id=node["id"], step=node["depth"], url=node["url"], bbox=bbox)


def drip_pricing(path: list[dict]) -> list[Finding]:
    """Fees that appear only at later steps of a purchase path, and total vs advertised price."""
    if len(path) < 2:
        return []
    first_seen = {}
    for node in path:
        for name, amt in FEE_RX.findall(node["snapshot"]["text"]):
            first_seen.setdefault(name.lower(), (node, amt))
    late = {k: v for k, v in first_seen.items() if v[0]["depth"] > 0}
    out = []
    advertised = prices(path[0]["snapshot"]["text"])
    final_text = path[-1]["snapshot"]["text"]
    totals = [prices(t)[0] for t in TOTAL_RX.findall(final_text) if prices(t)]
    if late:
        node = max((v[0] for v in late.values()), key=lambda n: n["depth"])
        ev = [f'"{k}" ({amt}) first appears at step {n["depth"]} — not on the first page' for k, (n, amt) in late.items()]
        if advertised and totals:
            ev.append(f"First price seen: {advertised[0]:g} → final total: {max(totals):g} (+{(max(totals)/advertised[0]-1)*100:.0f}%)")
        out.append(_f("drip_pricing", "Mandatory fees are revealed only late in the checkout flow.", 0.9, 0.75, ev, node))
    elif advertised and totals and max(totals) > advertised[0] * 1.08:
        out.append(_f("drip_pricing", "Final total is materially higher than the price first shown.", 0.6, 0.6,
                      [f"First price {advertised[0]:g} vs total {max(totals):g}"], path[-1]))
    return out


def obstruction(path: list[dict], goal: dict, reached: bool, max_depth: int) -> list[Finding]:
    if goal.get("kind") not in ("exit", "privacy"):
        return []
    out = []
    clicks = len(path) - 1
    interstitials = [n for n in path[1:-1] if RETENTION_RX.search(n["snapshot"]["text"][:1500])]
    ev = []
    for n in path[1:]:
        a = n.get("action") or {}
        note = f'Step {n["depth"]}: clicked "{short(a.get("text",""),60)}" → "{short(n["snapshot"].get("title") or n["url"],60)}"'
        if a.get("below_fold"):
            note += f' (control was below the fold at y={a["bbox"]["y"]}px — user had to scroll)'
        if n in interstitials:
            note += " [retention / guilt screen]"
        ev.append(note)
    if not reached:
        out.append(_f("obstruction", f'Goal "{goal["label"]}" could not be completed within {max_depth} steps.', 0.8, 0.9,
                      ev or ["No path to completion found"], path[-1]))
    elif clicks >= goal.get("fair_steps", 2) + 1 or interstitials:
        conf = min(0.5 + 0.12 * (clicks - goal.get("fair_steps", 2)) + 0.12 * len(interstitials), 0.97)
        ev.append(f'{clicks} clicks needed vs. a fair baseline of {goal.get("fair_steps", 2)}; {len(interstitials)} retention screen(s) on the way.')
        out.append(_f("obstruction", f'"{goal["label"]}" takes {clicks} steps through {len(interstitials)} retention screen(s).', conf, 0.8, ev,
                      interstitials[0] if interstitials else path[-1]))
    return out


def nagging(path: list[dict]) -> list[Finding]:
    overlay_steps = [n for n in path if any(o["cover"] > 0.25 for o in n["snapshot"].get("overlays", []))]
    if len(overlay_steps) >= 2:
        return [_f("nagging", f"Pop-ups interrupted the user on {len(overlay_steps)} of {len(path)} screens.", 0.75, 0.35,
                   [f'Step {n["depth"]}: overlay on "{short(n["snapshot"]["title"],50)}"' for n in overlay_steps], overlay_steps[-1])]
    return []


def audit_policy_clauses(policy_doc: dict) -> list[Finding]:
    """Scan Tavily-extracted Terms of Service or Cancellation FAQ for unfair contract traps."""
    if not policy_doc or not policy_doc.get("text"):
        return []
    text = policy_doc["text"]
    url = policy_doc.get("url", "")
    out = []

    # 1. Phone-only cancellation trap (Roach motel in fine print)
    phone_cancel = re.search(r"\b(cancel|terminate)\b[^\.\n]{0,80}\b(only by (calling|phone)|call our customer service|call 1-\d+|call us at)\b", text, re.I)
    if phone_cancel:
        out.append(Finding(
            pattern="obstruction",
            description="Fine print requires phone call to cancel a digital subscription (asymmetric exit).",
            confidence=0.88,
            severity=0.85,
            evidence=[f'Policy clause: "{phone_cancel.group(0)}"'],
            source="policy_doc",
            url=url,
        ))

    # 2. Forced renewal without notification / non-refundable fees
    auto_trap = re.search(r"\b(automatically renews?|recurring charge)[^\.\n]{0,100}\b(non-refundable|cannot be refunded|no refunds?)\b", text, re.I)
    if auto_trap:
        out.append(Finding(
            pattern="forced_continuity",
            description="Automatic recurring billing with strict non-refundable terms buried in fine print.",
            confidence=0.82,
            severity=0.80,
            evidence=[f'Policy clause: "{auto_trap.group(0)}"'],
            source="policy_doc",
            url=url,
        ))

    return out
