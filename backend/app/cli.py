"""Command line: python -m app.cli <url> --goal cancel_subscription --goal reject_cookies"""
import argparse
import json
import uuid
from datetime import datetime, timezone

from .agent.goals import GOALS
from .audit import run_audit, save_case, case_dir


def main():
    ap = argparse.ArgumentParser(description="DarkPattern Court — forensic UX audit")
    ap.add_argument("url")
    ap.add_argument("--goal", action="append", choices=list(GOALS), help="user goal(s) to simulate (default: explore)")
    ap.add_argument("--depth", type=int, default=6)
    ap.add_argument("--beam", type=int, default=2)
    ap.add_argument("--branching", type=int, default=3)
    a = ap.parse_args()
    case = {"id": datetime.now().strftime("%y%m%d") + "-" + uuid.uuid4().hex[:5], "url": a.url, "goals": a.goal or ["explore"],
            "max_depth": a.depth, "beam_width": a.beam, "branching": a.branching, "created_at": datetime.now(timezone.utc).isoformat()}
    save_case(case)
    c = run_audit(case)
    if c["status"] != "complete":
        print(c.get("error"))
        raise SystemExit(1)
    v = c["verdict"]
    print("\n" + "=" * 70 + f"\nVERDICT: {v['label']} — {v['summary']}\nManipulation score: {v['manipulation_score']}/100 (grade {v['grade']})")
    for ch in c["charges"]:
        print(f"  {ch['count_no']}: {ch['name']:<45} {ch['verdict']:<22} {ch['confidence']:.0%}")
    for j in c["journeys"]:
        print(f"\nTestimony — {j['label']}:")
        for s in j["steps"]:
            print(f"  Step {s['step']}: {s['testimony']}")
            for o in s["observations"]:
                print(f"      ⚠ {o}")
    print(f"\nReports: {case_dir(c['id']) / 'report.html'}\n         {case_dir(c['id']) / 'report.pdf'}")


if __name__ == "__main__":
    main()
