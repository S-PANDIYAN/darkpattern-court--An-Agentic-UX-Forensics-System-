"""The 'court': turns raw findings into charges, a narrative of the user's journey, citations of
the relevant authority (via RAG) and an overall verdict + manipulation score."""
from __future__ import annotations
from collections import defaultdict

from ..taxonomy import PATTERNS, pattern_name
from ..rag.retriever import retrieve
from ..utils import short


def verdict_label(conf: float) -> str:
    if conf >= 0.8:
        return "GUILTY"
    if conf >= 0.55:
        return "LIKELY"
    return "INSUFFICIENT EVIDENCE"


def build_charges(findings: list[dict]) -> list[dict]:
    by = defaultdict(list)
    for f in findings:
        by[f["pattern"]].append(f)
    charges = []
    for key, fs in by.items():
        fs.sort(key=lambda f: -f["confidence"])
        # independent corroboration: 1 - Π(1 - c), one vote per distinct (source, page) witness
        seen, p_not = set(), 1.0
        for f in fs:
            w = (f["source"], f.get("url"))
            if w in seen:
                continue
            seen.add(w)
            p_not *= (1 - f["confidence"])
        conf = round(1 - p_not, 2)
        sev = max(f["severity"] for f in fs)
        meta = PATTERNS.get(key, {})
        authorities = [{"id": d["id"], "source": d["source"], "url": d["url"], "excerpt": d["text"]} for d in retrieve(key, k=3)]
        try:
            from ..agent import scout
            if scout.is_tavily_available():
                for p in scout.find_legal_precedents(key)[:2]:
                    authorities.append({
                        "id": "LIVE-PRECEDENT",
                        "source": "Live Regulatory Precedent (Tavily)",
                        "url": p.get("url", ""),
                        "excerpt": f"{p.get('title')}: {p.get('summary')}",
                    })
        except Exception:
            pass

        charges.append({
            "pattern": key, "name": pattern_name(key), "category": meta.get("category"), "india_ccpa": meta.get("india_ccpa"),
            "charge": meta.get("charge"), "confidence": conf, "severity": sev, "verdict": verdict_label(conf),
            "count": len(fs), "sources": sorted({f["source"] for f in fs}),
            "exhibits": fs[:4],
            "authorities": authorities,
        })
    order = {"GUILTY": 0, "LIKELY": 1, "INSUFFICIENT EVIDENCE": 2}
    charges.sort(key=lambda c: (order[c["verdict"]], -c["severity"] * c["confidence"]))
    for i, c in enumerate(charges, 1):
        c["count_no"] = f"Count {i}"
    return charges


def narrate(path: list[dict], findings: list[dict], goal_label: str, reached: bool) -> list[dict]:
    """Courtroom-style step-by-step testimony of one simulated user journey."""
    by_node = defaultdict(list)
    for f in findings:
        by_node[f.get("node_id")].append(f)
    steps = []
    for n in path:
        if n["depth"] == 0:
            what = f'User opened "{short(n["title"] or n["url"], 70)}" intending to: {goal_label}.'
        else:
            a = n["action"]
            what = f'User clicked "{short(a["text"], 60)}" → arrived at "{short(n["title"] or n["url"], 60)}".'
            if a.get("below_fold"):
                what += f' The control was hidden below the fold (y={a["bbox"]["y"]}px) and required scrolling.'
        obs = [f'{pattern_name(f["pattern"])}: {f["evidence"][0] if f["evidence"] else f["description"]}' for f in by_node[n["id"]]
               if f["source"] != "path"]
        steps.append({"step": n["depth"], "node_id": n["id"], "url": n["url"], "title": n["title"], "testimony": what,
                      "observations": obs[:4], "screenshot": n.get("screenshot")})
    steps.append({"step": len(path), "node_id": None, "testimony": ("Goal reached." if reached else "Goal NOT reached — the user was trapped or gave up."),
                  "observations": [], "url": None, "title": None, "screenshot": None})
    return steps


def final_verdict(charges: list[dict]) -> dict:
    guilty = [c for c in charges if c["verdict"] == "GUILTY"]
    likely = [c for c in charges if c["verdict"] == "LIKELY"]
    score = 0.0
    for c in charges:
        score += c["confidence"] * c["severity"] * 25
    score = min(100, round(score))
    if guilty:
        summary = " + ".join(c["name"] for c in guilty[:4])
        label = "GUILTY"
    elif likely:
        summary = " + ".join(c["name"] for c in likely[:4])
        label = "LIKELY MANIPULATIVE"
    else:
        summary, label = "No manipulative pattern proven", "ACQUITTED"
    grade = "A" if score < 10 else "B" if score < 25 else "C" if score < 45 else "D" if score < 70 else "F"
    return {"label": label, "summary": summary, "manipulation_score": score, "grade": grade,
            "guilty_count": len(guilty), "likely_count": len(likely)}
