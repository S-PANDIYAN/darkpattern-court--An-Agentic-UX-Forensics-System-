"""FastAPI server: REST API for the dashboard, case artifacts, sample dark-pattern sites and the built React app."""
from __future__ import annotations
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config
from .agent.goals import GOALS
from .audit import run_audit, load_case, save_case
from .taxonomy import PATTERNS
from .rag.retriever import retrieve

app = FastAPI(title="DarkPattern Court API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
pool = ThreadPoolExecutor(max_workers=2)


class CaseIn(BaseModel):
    url: str
    goals: list[str] = Field(default_factory=lambda: ["explore"])
    max_depth: int = Field(default=config.DEFAULT_MAX_DEPTH, ge=1, le=12)
    beam_width: int = Field(default=config.DEFAULT_BEAM_WIDTH, ge=1, le=5)
    branching: int = Field(default=config.DEFAULT_BRANCHING, ge=1, le=6)


@app.get("/api/health")
def health():
    from .vision.ocr import OCR_AVAILABLE
    return {"ok": True, "ocr": OCR_AVAILABLE, "vision_llm": config.LLM_ENABLED}


@app.get("/api/meta")
def meta():
    return {"goals": {k: {"label": g["label"], "kind": g["kind"]} for k, g in GOALS.items()},
            "patterns": PATTERNS,
            "samples": [{"name": "ShopKart product → checkout", "url": "/samples/shop/product.html", "goals": ["checkout"]},
                        {"name": "StreamFlix cancel subscription", "url": "/samples/subscription/account.html", "goals": ["cancel_subscription"]},
                        {"name": "NewsDaily cookie banner", "url": "/samples/consent/index.html", "goals": ["reject_cookies"]},
                        {"name": "Mailer unsubscribe", "url": "/samples/newsletter/unsubscribe.html", "goals": ["unsubscribe"]},
                        {"name": "FairShop (control, no dark patterns)", "url": "/samples/fair/index.html", "goals": ["checkout", "reject_cookies"]}]}


@app.post("/api/cases")
def create_case(body: CaseIn):
    bad = [g for g in body.goals if g not in GOALS]
    if bad:
        raise HTTPException(400, f"Unknown goals: {bad}")
    case = {"id": datetime.now().strftime("%y%m%d") + "-" + uuid.uuid4().hex[:5], **body.model_dump(),
            "status": "queued", "created_at": datetime.now(timezone.utc).isoformat(), "log": []}
    save_case(case)
    pool.submit(run_audit, case)
    return {"id": case["id"], "status": "queued"}


@app.get("/api/cases")
def list_cases():
    out = []
    for d in sorted(config.CASES_DIR.iterdir(), reverse=True):
        c = load_case(d.name) if d.is_dir() else None
        if c:
            out.append({k: c.get(k) for k in ("id", "url", "goals", "status", "created_at")} | {"verdict": c.get("verdict")})
    return out


@app.get("/api/cases/{cid}")
def get_case(cid: str):
    c = load_case(cid)
    if not c:
        raise HTTPException(404, "case not found")
    return c


@app.get("/api/cases/{cid}/files/{path:path}")
def case_file(cid: str, path: str):
    base = (config.CASES_DIR / cid).resolve()
    f = (base / path).resolve()
    if base not in f.parents or not f.exists():
        raise HTTPException(404)
    return FileResponse(f)


@app.get("/api/rag")
def rag(q: str = "", pattern: str | None = None, k: int = 5):
    return retrieve(pattern, q, k)


app.mount("/samples", StaticFiles(directory=config.SAMPLES_DIR, html=True), name="samples")
if config.FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=config.FRONTEND_DIST, html=True), name="ui")
