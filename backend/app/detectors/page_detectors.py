"""Rule-based UI-component detectors that run on a single page snapshot.

Each detector is a function(snapshot, ctx) -> list[Finding]. They are deliberately
explainable: every Finding carries the exact quote / measurement used as evidence,
which is what the court needs to build an exhibit.
"""
from __future__ import annotations
import re
from ..models import Finding
from ..utils import contrast_ratio, saturation, short, prices, norm, parse_rgb

DETECTORS = []


def detector(fn):
    DETECTORS.append(fn)
    return fn


def _rx(*parts):
    return re.compile("|".join(parts), re.I)


URGENCY_RX = _rx(r"\b(offer|sale|deal|price|discount)s?\s+(ends|expires?|ending)\b", r"\bhurry\b", r"\blimited[- ]time\b",
                 r"\bending soon\b", r"\blast chance\b", r"\bonly\s+\d+\s+(minutes?|hours?|mins?)\b", r"\bact now\b",
                 r"\b(expires|ends) in\b", r"\btoday only\b")
TIMER_RX = re.compile(r"\b\d{1,2}:\d{2}(:\d{2})?\b")
SCARCITY_RX = _rx(r"\bonly\s+\d+\s+(left|remaining|in stock)\b", r"\b\d+\s+left in stock\b", r"\balmost (gone|sold out)\b",
                  r"\bselling fast\b", r"\blow stock\b", r"\bhigh demand\b")
SOCIAL_RX = _rx(r"\b\d+\s+(people|others|users|shoppers|customers)\s+(are\s+)?(viewing|looking|watching|bought|purchased|have this in)",
                r"\bsomeone (in|from) [\w ]+ (just )?(bought|purchased|ordered)\b", r"\bjust (bought|purchased) this\b")
CONSENT_RX = _rx(r"newsletter", r"marketing", r"offers?", r"promotion", r"partners?", r"third[- ]part", r"\bshare\b", r"personali[sz]",
                 r"analytics", r"advertis", r"tracking", r"cookies?", r"\bemails?\b", r"\bsms\b", r"updates")
MONEY_RX = _rx(r"protection", r"insurance", r"warranty", r"donat", r"\btip\b", r"premium", r"priority", r"add[- ]on", r"upgrade",
               r"gift wrap", r"auto[- ]?renew", r"subscribe and save", r"membership")
SHAME_RX = _rx(r"no,?\s*thanks?,?\s*i\b", r"\bi\s*(don'?t|do not)\s+(want|like|care|need)", r"\bi\s*(prefer|'d rather|would rather)\s+(paying|to pay|miss|lose|not)",
               r"\bfull price\b", r"\bi('?ll| will)\s+(pass|miss|stay (uninformed|behind))", r"\bi (hate|don'?t like) (saving|deals|money)",
               r"\bi('?m| am) (not interested in|fine with) (saving|being)", r"\blose (my|all)\b", r"\bno,? i('?m| am) (ok|okay|fine)\b")
ACCEPT_RX = _rx(r"^\s*(accept|agree|allow|i agree|got it|ok(ay)?|yes|continue|keep|stay|claim|yes,? keep)\b", r"accept all", r"allow all")
REJECT_RX = _rx(r"\b(reject|decline|deny|refuse|necessary only|only necessary|essential only|manage|preferences|settings|options|customi[sz]e|no thanks|cancel|unsubscribe|opt out)\b")
MATERIAL_RX = _rx(r"auto[- ]?renew", r"automatically (renew|charged|billed|continue)", r"recurring", r"will be (charged|billed)",
                  r"non[- ]refundable", r"\bfees?\b", r"cancel(lation)?", r"per (month|year)", r"after (the )?(free )?trial", r"billed (monthly|annually)")
TRIAL_RX = _rx(r"free trial", r"try (it )?free", r"\bfree for \d+", r"\$0 today", r"₹0 today", r"first month free")
RENEW_RX = _rx(r"auto[- ]?renew", r"automatically", r"will be (charged|billed)", r"recurring", r"unless (you )?cancel")
TRICK_RX = _rx(r"\b(uncheck|untick|do not check|don'?t check|leave (this )?(un)?checked)\b.{0,60}\b(not|don'?t|no)\b",
               r"\bif you (do not|don'?t) (want|wish)\b.{0,60}\b(un)?(check|tick)\b",
               r"\b(not|don'?t)\b.{0,25}\b(not|don'?t|un\w+)\b.{0,25}\b(receive|opt|email)")
FORCED_RX = _rx(r"\b(must|need to|required to|have to)\s+(create an account|sign up|register|log ?in|allow|enable|share|download)",
                r"\bsign up to (continue|view|see)\b", r"\bcreate an account to (continue|checkout|proceed)\b")


def _find_text(snap, rx, ctx):
    hits = []
    for t in snap.get("texts", []):
        if rx.search(t["text"]):
            hits.append(t)
    for line in ctx.get("ocr_only_lines", []):
        if rx.search(line):
            hits.append({"text": line, "bbox": None, "ocr": True})
    return hits


def _f(pattern, desc, conf, sev, ev, ctx, bbox=None, source="dom"):
    return Finding(pattern=pattern, description=desc, confidence=round(min(conf, 0.99), 2), severity=sev,
                   evidence=ev, source=source, node_id=ctx.get("node_id"), step=ctx.get("step"),
                   url=ctx.get("url"), bbox=bbox)


# --------------------------------------------------------------------- induce false beliefs
@detector
def false_urgency(snap, ctx):
    out = []
    hits = _find_text(snap, URGENCY_RX, ctx)
    has_timer = bool(TIMER_RX.search(snap.get("text", "")))
    probe = ctx.get("probe") or {}
    tb, ta = probe.get("timers_before", []), probe.get("timers_after", [])
    reset = bool(tb and ta and max(ta) >= max(tb) - 1)
    for h in hits[:2]:
        ev = [f'Urgency claim: "{short(h["text"])}"']
        conf = 0.55 + (0.15 if has_timer else 0)
        if reset:
            ev.append(f"Forensic reload test: countdown read {max(tb)}s, after {probe.get('elapsed_s')}s + reload it read {max(ta)}s "
                      f"(timer restarted instead of continuing).")
            conf = 0.95
        out.append(_f("false_urgency", "Time-pressure messaging found" + (" and the countdown resets on reload — the deadline is fake." if reset else "."),
                      conf, 0.6, ev, ctx, h.get("bbox"), "temporal" if reset else ("ocr" if h.get("ocr") else "dom")))
    if not hits and reset:
        out.append(_f("false_urgency", "Countdown timer resets on reload.", 0.85, 0.6,
                      [f"Timer {max(tb)}s → {max(ta)}s after reload"], ctx, None, "temporal"))
    return out


@detector
def fake_scarcity(snap, ctx):
    probe = ctx.get("probe") or {}
    changed = probe.get("counters_before") and probe.get("counters_before") != probe.get("counters_after")
    out = []
    for h in _find_text(snap, SCARCITY_RX, ctx)[:2]:
        ev = [f'Scarcity claim: "{short(h["text"])}"']
        if changed:
            ev.append(f"Reload test: {probe['counters_before']} → {probe['counters_after']} (values change randomly).")
        out.append(_f("fake_scarcity", "Low-stock / high-demand claim used as pressure.", 0.85 if changed else 0.55, 0.45, ev, ctx, h.get("bbox")))
    return out


@detector
def fake_social_proof(snap, ctx):
    probe = ctx.get("probe") or {}
    changed = probe.get("counters_before") and probe.get("counters_before") != probe.get("counters_after")
    out = []
    for h in _find_text(snap, SOCIAL_RX, ctx)[:2]:
        ev = [f'Activity message: "{short(h["text"])}"']
        if changed:
            ev.append(f"Reload test: {probe['counters_before']} → {probe['counters_after']} (numbers regenerate on every load).")
        out.append(_f("fake_social_proof", "Activity / popularity notification that appears fabricated.", 0.88 if changed else 0.5, 0.4, ev, ctx, h.get("bbox")))
    return out


@detector
def confirmshaming(snap, ctx):
    out = []
    for el in snap.get("elements", []):
        if el["visible"] and el["text"] and SHAME_RX.search(el["text"]) and len(el["text"]) < 160:
            out.append(_f("confirmshaming", "Decline option is worded to shame the user.", 0.85, 0.5,
                          [f'Decline control reads: "{short(el["text"])}"'], ctx, el["bbox"]))
    return out


# --------------------------------------------------------------------- privacy & charges
@detector
def preselected_options(snap, ctx):
    out = []
    for el in snap.get("elements", []):
        if not el.get("checked"):
            continue
        label = norm(el["text"])
        has_price = bool(prices(label)) or "+" in label and bool(re.search(r"\d", label))
        if MONEY_RX.search(label) or has_price:
            out.append(_f("basket_sneaking", "A paid extra is pre-selected and will be charged unless the user notices and removes it.",
                          0.9 if has_price else 0.75, 0.8, [f'Pre-checked paid option: "{short(label)}"'], ctx, el["bbox"]))
        elif CONSENT_RX.search(label):
            out.append(_f("preselected_consent", "Consent / marketing option is opted-in by default.", 0.85, 0.55,
                          [f'Pre-checked consent: "{short(label)}"'], ctx, el["bbox"]))
    return out


def _prominence(el):
    area = max(el["bbox"]["w"] * el["bbox"]["h"], 1)
    own = parse_rgb(el.get("ownBg"))
    filled = el.get("ownBg") and not re.search(r",\s*0\)$", el.get("ownBg", "")) and el.get("ownBg") != "rgba(0, 0, 0, 0)"
    contrast = contrast_ratio(el["color"], el["bg"])
    weight = 1.2 if el.get("fontWeight", 400) >= 600 else 1.0
    color_boost = 1 + saturation(own) if filled and own else 1.0
    return area * (contrast / 4.5) * weight * (2.0 if filled else 1.0) * color_boost, contrast, filled


@detector
def asymmetric_choice(snap, ctx):
    els = [e for e in snap.get("elements", []) if e["visible"] and e["text"] and e["tag"] in ("button", "a", "input", "summary") and e.get("checked") is None]
    accepts = [e for e in els if ACCEPT_RX.search(e["text"]) and len(e["text"]) < 60]
    rejects = [e for e in els if REJECT_RX.search(e["text"]) and not ACCEPT_RX.search(e["text"]) and len(e["text"]) < 80]
    out = []
    if not accepts:
        return out
    acc = max(accepts, key=lambda e: _prominence(e)[0])
    pa, ca, fa = _prominence(acc)
    consentish = re.search(r"cookie|consent|tracking|personal data", snap.get("text", ""), re.I)
    if not rejects:
        if consentish and re.search(r"accept|agree|allow", acc["text"], re.I):
            out.append(_f("interface_interference", "A consent prompt offers a prominent accept button but no reject option on the first layer.",
                          0.8, 0.6, [f'Accept control: "{short(acc["text"])}"', "No equivalent 'Reject' control on this screen."], ctx, acc["bbox"]))
        return out
    rej = max(rejects, key=lambda e: _prominence(e)[0])
    pr, cr, fr = _prominence(rej)
    ratio = pa / max(pr, 1)
    below_fold = rej["bbox"]["y"] > snap["viewport"]["h"] and acc["bbox"]["y"] <= snap["viewport"]["h"]
    if ratio >= 3 or (cr < 3 and ca >= 4.5) or below_fold:
        ev = [f'Preferred option "{short(acc["text"],50)}": {acc["bbox"]["w"]}×{acc["bbox"]["h"]}px, contrast {ca}:1, {"filled button" if fa else "plain"}',
              f'Alternative "{short(rej["text"],50)}": {rej["bbox"]["w"]}×{rej["bbox"]["h"]}px, contrast {cr}:1, {"filled button" if fr else "text link"}, font {rej["fontSize"]:.0f}px',
              f"Visual prominence ratio ≈ {ratio:.1f}×"]
        if cr < 4.5:
            ev.append(f"Alternative fails WCAG AA text contrast (4.5:1) with {cr}:1.")
        if below_fold:
            ev.append(f'Alternative sits below the fold (y={rej["bbox"]["y"]}px, viewport {snap["viewport"]["h"]}px).')
        conf = min(0.5 + ratio / 20 + (0.15 if cr < 3 else 0) + (0.15 if below_fold else 0), 0.97)
        out.append(_f("interface_interference", "The option that benefits the business is visually dominant; the alternative is de-emphasised.",
                      conf, 0.55, ev, ctx, {"x": min(acc["bbox"]["x"], rej["bbox"]["x"]), "y": min(acc["bbox"]["y"], rej["bbox"]["y"]),
                                             "w": max(acc["bbox"]["x"] + acc["bbox"]["w"], rej["bbox"]["x"] + rej["bbox"]["w"]) - min(acc["bbox"]["x"], rej["bbox"]["x"]),
                                             "h": max(acc["bbox"]["y"] + acc["bbox"]["h"], rej["bbox"]["y"] + rej["bbox"]["h"]) - min(acc["bbox"]["y"], rej["bbox"]["y"])}))
    return out


@detector
def hidden_information(snap, ctx):
    out = []
    for t in snap.get("texts", []):
        if not MATERIAL_RX.search(t["text"]):
            continue
        cr = contrast_ratio(t["color"], t["bg"])
        small = t["fontSize"] < 11
        if small or cr < 3:
            control = t["tag"] in ("a", "button")
            ev = [f'{"Exit / material control" if control else "Material term"}: "{short(t["text"])}"', f'Font size {t["fontSize"]:.0f}px, contrast {cr}:1']
            out.append(_f("hidden_information", "The cancellation / material control is rendered in small, low-contrast text." if control
                          else "Material terms are displayed in fine print / low-contrast text.",
                          0.6 + (0.15 if small else 0) + (0.15 if cr < 3 else 0), 0.65, ev, ctx, t["bbox"]))
    return out[:3]


@detector
def forced_continuity(snap, ctx):
    text = snap.get("text", "")
    if not (TRIAL_RX.search(text) and RENEW_RX.search(text)):
        return []
    hidden = [t for t in snap.get("texts", []) if RENEW_RX.search(t["text"]) and (t["fontSize"] < 11 or contrast_ratio(t["color"], t["bg"]) < 3)]
    trial = next((t for t in snap.get("texts", []) if TRIAL_RX.search(t["text"])), None)
    ev = [f'Offer: "{short(trial["text"]) if trial else "free trial"}"']
    if hidden:
        ev.append(f'Renewal disclosure only in fine print: "{short(hidden[0]["text"])}" ({hidden[0]["fontSize"]:.0f}px)')
    return [_f("forced_continuity", "Free trial converts to a paid recurring plan" + (" and the renewal terms are hidden." if hidden else "."),
               0.9 if hidden else 0.5, 0.8, ev, ctx, (hidden[0] if hidden else trial or {}).get("bbox"))]


@detector
def trick_question(snap, ctx):
    out = []
    for h in _find_text(snap, TRICK_RX, ctx)[:2]:
        out.append(_f("trick_question", "Confusing / double-negative wording around a choice.", 0.75, 0.5,
                      [f'Wording: "{short(h["text"])}"'], ctx, h.get("bbox")))
    return out


@detector
def forced_action(snap, ctx):
    return [_f("forced_action", "User must perform an unrelated action to proceed.", 0.7, 0.5,
               [f'"{short(h["text"])}"'], ctx, h.get("bbox")) for h in _find_text(snap, FORCED_RX, ctx)[:1]]


@detector
def nagging_overlay(snap, ctx):
    promo = [o for o in snap.get("overlays", []) if o["cover"] > 0.25 and re.search(r"offer|subscribe|sign up|discount|% off|app|notification|newsletter|wait", o["text"], re.I)]
    if promo:
        o = promo[0]
        return [_f("nagging", "A promotional modal interrupts the task.", 0.5, 0.3,
                   [f'Overlay covering {int(o["cover"]*100)}% of the viewport: "{short(o["text"], 100)}"'], ctx, o["bbox"])]
    return []


def run_page_detectors(snap: dict, ctx: dict) -> list[Finding]:
    findings = []
    for fn in DETECTORS:
        try:
            findings.extend(fn(snap, ctx))
        except Exception as exc:  # a broken detector must never break the audit
            print(f"[detector {fn.__name__}] {exc}")
    return findings
