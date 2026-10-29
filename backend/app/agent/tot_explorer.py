"""Tree-of-Thought route exploration.

Every node of the tree is a page state reached by a sequence of clicks. At each node the
agent (1) proposes candidate thoughts (= clickable actions), (2) evaluates each thought with a
value function (goal-keyword heuristic, optionally blended with an LLM judgement), (3) keeps
the best `branching` thoughts and prunes the rest with an explicit rationale, and (4) runs a
beam search across depth levels. This lets it simulate *different* user decision paths (e.g. the
user who accepts the retention offer vs. the user who insists on cancelling) and keeps the whole
reasoning tree as evidence of what alternatives existed on each screen.
"""
from __future__ import annotations
import re
import uuid
from typing import Callable
from urllib.parse import urlparse

from .. import config
from ..vision import vlm
from . import browser as B
from .goals import GOALS


def _score(el: dict, goal: dict, snap: dict) -> tuple[float, str]:
    text = (el["text"] or "").lower().strip()
    if el.get("disabled"):
        return -99, "disabled control"
    if not text:
        # Check if it has an href or is a button/toggle
        if el["tag"] == "button" or el.get("role") == "button":
            text = (el.get("aria-label") or el.get("title") or "").lower().strip()
            if not text:
                return -10, "empty control without label"
        else:
            return -99, "empty control"

    # Allow same domain / subdomains (e.g. checkout.domain.com, auth.domain.com)
    is_same_site = el.get("sameDomain", el.get("sameOrigin", True))
    if el["tag"] == "a" and (el["href"].startswith(("mailto:", "tel:", "javascript:void")) or not is_same_site):
        return -99, "leaves the site under audit"
    if el.get("checked") is not None:
        return -50, "toggle, not a navigation step (inspected by detectors instead)"
    best, why = 0.0, []
    for kw, w in goal["positive"].items():
        if kw in text:
            if w > best:
                best = w
            why.append(f"+{w} '{kw}'")
    for kw, w in goal["negative"].items():
        if kw in text:
            best += w
            why.append(f"{w} '{kw}'")
    if best <= 0 and not why:
        return 0.5 if el["tag"] == "button" else 0.1, "no goal signal"
    if len(text) > 60:
        best -= 2
        why.append("-2 long text")
    return best, ", ".join(why)


def _action(el: dict, vh: int) -> dict:
    return {"id": el.get("id", ""), "tag": el["tag"], "type": el.get("type", ""), "text": el["text"],
            "href": el.get("href", ""), "bbox": el["bbox"], "below_fold": el["bbox"]["y"] > vh}


class TreeOfThoughtExplorer:
    def __init__(self, start_url: str, goal_key: str, case_dir, max_depth=None, beam_width=None,
                 branching=None, log: Callable[[str], None] = print, on_node: Callable[[dict, object], None] | None = None):
        self.start_url = start_url
        self.goal_key = goal_key
        self.goal = GOALS[goal_key]
        self.case_dir = case_dir
        self.max_depth = max_depth or config.DEFAULT_MAX_DEPTH
        self.beam_width = beam_width or config.DEFAULT_BEAM_WIDTH
        self.branching = branching or config.DEFAULT_BRANCHING
        self.log = log
        self.on_node = on_node        # callback(node, page) for page-level analysis + screenshots
        self.nodes: dict[str, dict] = {}
        self.host = urlparse(start_url).netloc

    def _success(self, snap: dict) -> bool:
        return any(re.search(rx, snap["text"], re.I) for rx in self.goal["success"])

    def _visit(self, browser, actions, parent, depth, thought) -> dict | None:
        page = B.replay(browser, self.start_url, [a for a in actions])
        if page is None:
            return None
        snap = B.snapshot(page)
        title = (snap.get("title") or "").strip()
        if not title:
            title = urlparse(snap.get("url", "")).path or snap.get("url", "") or "Page"
        node = {"id": f"{self.goal_key[:3]}-{uuid.uuid4().hex[:6]}", "parent": parent, "depth": depth, "url": snap["url"],
                "title": title, "action": actions[-1] if actions else None, "actions": actions,
                "thought": thought, "status": "expanded", "children": [], "pruned": [], "snapshot": snap,
                "goal_reached": self._success(snap), "value": 0.0}
        self.nodes[node["id"]] = node
        if parent:
            self.nodes[parent]["children"].append(node["id"])
        if self.on_node:
            self.on_node(node, page)
        if node["goal_reached"]:
            node["status"] = "goal"
        try:
            page.close()
        except Exception:
            pass
        return node

    def _propose(self, node) -> list[dict]:
        snap = node["snapshot"]
        vh = snap["viewport"]["h"]
        seen, cands = set(), []
        visited = {self.nodes[a]["url"].split("#")[0] for a in self._ancestors(node)} | {snap["url"].split("#")[0]}
        for el in snap["elements"]:
            if not el["visible"]:
                continue
            key = (el["tag"], el["text"])
            if key in seen:
                continue
            seen.add(key)
            s, why = _score(el, self.goal, snap)
            if s <= -50:
                continue
            if el["tag"] == "a" and el.get("abs") and el["abs"].split("#")[0] in visited:
                s -= 4
                why += ", -4 returns to an already visited page"
            cands.append({"action": _action(el, vh), "score": s, "rationale": why})
        cands.sort(key=lambda c: -c["score"])
        if config.LLM_ENABLED and cands:
            try:
                som_shot = node.get("som_screenshot")
                if som_shot:
                    vlm.decide_som_action(self.goal["label"], snap, som_shot, cands)
                cands = vlm.rerank_thoughts(self.goal["label"], snap, cands[:8]) + cands[8:]
            except Exception as exc:
                self.log(f"[{self.goal_key}] Warning: LLM reranking skipped: {exc}")
        return cands

    def run(self, browser) -> dict:
        root = self._visit(browser, [], None, 0, {"text": "Open start page", "score": 0, "rationale": "start"})
        if root is None:
            raise RuntimeError("Could not open start URL")
        # Update start_url to resolved landing page (handles redirects e.g. zeptonow.com -> zepto.com)
        if root.get("url"):
            self.start_url = root["url"]
        self.log(f"[{self.goal_key}] root: {root['title']}")
        frontier = [root]
        for depth in range(1, self.max_depth + 1):
            if any(n["goal_reached"] for n in self.nodes.values()) and self.goal["success"]:
                break
            nxt = []
            for node in frontier:
                if node["goal_reached"]:
                    continue
                cands = self._propose(node)
                keep = [c for c in cands if c["score"] > 0][: self.branching]
                for c in cands[len(keep): len(keep) + 6]:
                    node["pruned"].append({"text": c["action"]["text"][:80], "score": c["score"],
                                           "reason": c["rationale"] if c["score"] <= 0 else "outside beam (lower value)"})
                if not keep:
                    node["status"] = "dead_end"
                for c in keep:
                    if len(self.nodes) >= config.MAX_NODES:
                        break
                    child = self._visit(browser, node["actions"] + [c["action"]], node["id"], depth,
                                        {"text": c["action"]["text"][:80], "score": c["score"], "rationale": c["rationale"]})
                    if child is None:
                        continue
                    child["value"] = node["value"] + c["score"] + (100 if child["goal_reached"] else 0)
                    # loop detection: same URL+title as an ancestor with no new content
                    if any(self.nodes[a]["url"] == child["url"] and self.nodes[a]["snapshot"]["text"][:500] == child["snapshot"]["text"][:500]
                           for a in self._ancestors(child)):
                        child["status"] = "loop"
                        continue
                    self.log(f"[{self.goal_key}] d{depth} '{c['action']['text'][:40]}' -> {child['title']} (v={child['value']:.1f}{', GOAL' if child['goal_reached'] else ''})")
                    nxt.append(child)
            nxt.sort(key=lambda n: -n["value"])
            for n in nxt[self.beam_width:]:
                if not n["goal_reached"]:
                    n["status"] = "beam_pruned"
            frontier = [n for n in nxt[: self.beam_width]] + [n for n in nxt[self.beam_width:] if n["goal_reached"]]
            if not frontier:
                break
        return self.result()

    def _ancestors(self, node):
        out, p = [], node["parent"]
        while p:
            out.append(p)
            p = self.nodes[p]["parent"]
        return out

    def path_to(self, nid) -> list[dict]:
        chain = [self.nodes[nid]] + [self.nodes[a] for a in self._ancestors(self.nodes[nid])]
        return list(reversed(chain))

    def result(self) -> dict:
        goals = [n for n in self.nodes.values() if n["goal_reached"]]
        if goals:
            best = min(goals, key=lambda n: (n["depth"], -n["value"]))
            reached = True
        else:
            leaves = [n for n in self.nodes.values() if not n["children"] and n["status"] != "loop"] or list(self.nodes.values())
            best = max(leaves, key=lambda n: (n["value"], n["depth"]))
            reached = False
        alt_paths = [self.path_to(n["id"]) for n in self.nodes.values() if not n["children"] and n["id"] != best["id"] and n["status"] != "loop"]
        return {"goal": self.goal_key, "reached": reached, "best_path": self.path_to(best["id"]), "alt_paths": alt_paths}
