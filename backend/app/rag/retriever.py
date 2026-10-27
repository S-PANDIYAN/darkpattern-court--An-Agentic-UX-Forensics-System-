"""Guideline RAG: a dependency-free BM25 retriever over a curated knowledge base of FTC staff
guidance, statutes and international equivalents. Passages are tagged with taxonomy keys so a
charge can cite the most relevant authority. Swap in an embedding store (e.g. Chroma/FAISS)
by implementing the same `retrieve()` signature."""
from __future__ import annotations
import json
import math
import re
from collections import Counter
from functools import lru_cache

from .. import config
from ..taxonomy import PATTERNS

TOK = re.compile(r"[a-z0-9]+")
STOP = set("the a an of to and or in on for is are be by with that as at this from it its not".split())


def _tok(t):
    return [w for w in TOK.findall(t.lower()) if w not in STOP]


@lru_cache(maxsize=1)
def _index():
    docs = json.loads(config.KB_PATH.read_text())
    toks = [_tok(d["source"] + " " + d["text"]) for d in docs]
    df = Counter(w for t in toks for w in set(t))
    avg = sum(map(len, toks)) / len(toks)
    return docs, toks, df, avg


def bm25(query: str, k1=1.5, b=0.75):
    docs, toks, df, avg = _index()
    q = _tok(query)
    n = len(docs)
    scores = []
    for d, t in zip(docs, toks):
        tf = Counter(t)
        s = 0.0
        for w in q:
            if w in tf:
                idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                s += idf * tf[w] * (k1 + 1) / (tf[w] + k1 * (1 - b + b * len(t) / avg))
        scores.append(s)
    return list(zip(docs, scores))


def retrieve(pattern: str | None = None, query: str = "", k: int = 3) -> list[dict]:
    q = query or (PATTERNS.get(pattern, {}).get("query", "") if pattern else "")
    ranked = []
    for d, s in bm25(q):
        if pattern and pattern in d["patterns"]:
            s = s * 1.5 + 2.0
        # prefer specific authorities over the general overview
        s -= 0.15 * len(d["patterns"])
        ranked.append((s, d))
    ranked.sort(key=lambda x: -x[0])
    return [{**d, "score": round(s, 2)} for s, d in ranked[:k] if s > 0]
