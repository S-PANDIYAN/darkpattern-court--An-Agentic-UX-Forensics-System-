"""End-to-end forensic audit pipeline:
   browse (Playwright) → ToT route exploration per goal → snapshot + screenshot + OCR + VLM per
   page state → page & path detectors → exhibits → charges + RAG citations → verdict → reports."""
from __future__ import annotations
import json
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .agent import browser as B
from .agent import captcha, auth
from .agent.goals import GOALS
from .agent.tot_explorer import TreeOfThoughtExplorer
from .court.exhibits import make_exhibit
from .court.verdict import build_charges, narrate, final_verdict
from .detectors.page_detectors import run_page_detectors
from .detectors import path_detectors as PD
from .taxonomy import pattern_name
from .vision import ocr, vlm
from . import report


def case_dir(case_id: str) -> Path:
    return config.CASES_DIR / case_id


def load_case(case_id: str) -> dict | None:
    p = case_dir(case_id) / "case.json"
    return json.loads(p.read_text()) if p.exists() else None


def save_case(case: dict):
    d = case_dir(case["id"])
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "case.json.tmp"
    tmp.write_text(json.dumps(case, indent=1, default=str))
    tmp.replace(d / "case.json")


def _node_summary(n):
    return {k: n.get(k) for k in ("id", "parent", "depth", "url", "title", "thought", "status", "children", "pruned",
                                  "goal_reached", "value", "screenshot", "action")} | {"finding_count": len(n.get("findings", []))}


def run_audit(case: dict) -> dict:
    cid = case["id"]
    d = case_dir(cid)
    (d / "shots").mkdir(parents=True, exist_ok=True)
    (d / "exhibits").mkdir(exist_ok=True)
    case.update(status="running", started_at=datetime.now(timezone.utc).isoformat(), log=[])

    def log(msg):
        case["log"].append(f"{time.strftime('%H:%M:%S')} {msg}")
        try:
            print(f"[{cid}] {msg}")
        except Exception:
            try:
                print(f"[{cid}] {msg.encode('ascii', 'replace').decode('ascii')}")
            except Exception:
                pass
        save_case(case)

    findings: list[dict] = []
    seen_keys, probed = set(), {}
    journeys, trees = [], {}
    capabilities = {"ocr": ocr.OCR_AVAILABLE, "vision_llm": config.LLM_ENABLED}
    case["capabilities"] = capabilities

    def add(fs):
        for f in fs:
            fd = f.to_dict() if hasattr(f, "to_dict") else f
            key = (fd["pattern"], (fd.get("url") or "").split("#")[0], (fd["evidence"] or [""])[0][:80])
            if key in seen_keys:
                continue
            seen_keys.add(key)
            findings.append(fd)

    try:
        with B.Browser() as br:
            for goal_key in case["goals"]:
                goal = GOALS[goal_key]
                log(f"Simulating user goal: {goal['label']}")

                def on_node(node, page):
                    # 1. Primary screenshot with Set-of-Marks visual badges (visible in UI & reports)
                    shot = d / "shots" / f"{node['id']}.png"
                    B.screenshot(page, shot, with_marks=True)
                    node["screenshot"] = f"shots/{node['id']}.png"
                    node["som_screenshot"] = str(shot)

                    # Also save clean un-annotated screenshot for forensic crops
                    clean_shot = d / "shots" / f"{node['id']}_clean.png"
                    B.screenshot(page, clean_shot, with_marks=False)
                    node["clean_screenshot"] = str(clean_shot)

                    snap = node["snapshot"]

                    # 1. Automated CAPTCHA solving using Kaggle GPU LLaVA-13B
                    cap_info = captcha.detect_captcha(page, snap)
                    if cap_info:
                        log(f"CAPTCHA verification detected on {page.url}. Solving via GPU LLaVA-13B...")
                        if captcha.solve_and_submit_captcha(page, cap_info, d / "shots", log_fn=log):
                            B.settle(page)
                            snap = B.snapshot(page)
                            node["snapshot"] = snap

                    # 2. Human-in-the-loop Login Wall handling
                    auth_info = auth.detect_login_gate(page, snap)
                    if auth_info:
                        log(f"Login gate detected: '{auth_info['title']}'. Awaiting user credentials / authentication...")
                        if auth.wait_for_user_login(page, auth_info, timeout_s=45, log_fn=log):
                            B.settle(page)
                            snap = B.snapshot(page)
                            node["snapshot"] = snap

                    base_url = snap["url"].split("#")[0]
                    if base_url not in probed:
                        probed[base_url] = B.temporal_probe(page) if (B.TIMER_RE.search(snap["text"]) or B.COUNTER_RE.search(snap["text"])) else {}
                    ctx = {"node_id": node["id"], "step": node["depth"], "url": snap["url"], "probe": probed[base_url],
                           "ocr_only_lines": ocr.ocr_only_lines(shot, snap["text"]) if ocr.OCR_AVAILABLE else []}
                    fs = run_page_detectors(snap, ctx) + vlm.analyse_screenshot(shot, ctx)
                    node["findings"] = [f.pattern for f in fs]
                    add(fs)

                ex = TreeOfThoughtExplorer(case["url"], goal_key, d, case.get("max_depth"), case.get("beam_width"),
                                           case.get("branching"), log=log, on_node=on_node)
                res = ex.run(br)
                best = res["best_path"]
                path_fs = PD.obstruction(best, goal, res["reached"], ex.max_depth) + PD.nagging(best)
                for p in [best] + res["alt_paths"]:
                    if goal["kind"] == "purchase" or goal_key == "explore":
                        path_fs += PD.drip_pricing(p)
                add(path_fs)
                journeys.append({"goal": goal_key, "label": goal["label"], "reached": res["reached"], "clicks": len(best) - 1,
                                 "path": [n["id"] for n in best], "steps": narrate(best, findings, goal["label"], res["reached"]),
                                 "alternatives": [{"path": [n["id"] for n in p], "end": p[-1]["title"], "reached": p[-1]["goal_reached"]}
                                                  for p in res["alt_paths"][:6]]})
                trees[goal_key] = {nid: _node_summary(n) for nid, n in ex.nodes.items()}
                log(f"Goal '{goal['label']}': {'reached' if res['reached'] else 'NOT reached'} in {len(best)-1} clicks; "
                    f"{len(ex.nodes)} states explored")

        # exhibits
        shots_by_node = {nid: n["screenshot"] for t in trees.values() for nid, n in t.items()}
        for i, f in enumerate(findings, 1):
            f["id"] = f"E{i:02d}"
            shot = shots_by_node.get(f.get("node_id"))
            if shot:
                out = d / "exhibits" / f"{f['id']}.png"
                if make_exhibit(d / shot, f.get("bbox"), out, f"Exhibit {f['id']} — {pattern_name(f['pattern'])} — step {f.get('step')}"):
                    f["exhibit"] = f"exhibits/{f['id']}.png"
        charges = build_charges(findings)
        case.update(findings=findings, charges=charges, journeys=journeys, trees=trees, verdict=final_verdict(charges),
                    status="complete", finished_at=datetime.now(timezone.utc).isoformat())
        log(f"Verdict: {case['verdict']['label']} — {case['verdict']['summary']} (score {case['verdict']['manipulation_score']})")
        report.write_html(case, d / "report.html")
        report.write_pdf(case, d / "report.pdf")
        log("Reports written (report.html, report.pdf)")
    except Exception as exc:
        case.update(status="error", error=f"{exc}\n{traceback.format_exc()[-1500:]}")
        log(f"ERROR: {exc}")
    save_case(case)
    return case
