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
from .taxonomy import PATTERNS, pattern_name
from .court.verdict import build_charges, final_verdict
from .rag.retriever import retrieve
from . import report

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


class ExtensionFindingIn(BaseModel):
    category: str
    text: str
    confidence: float = 0.95
    severity: float = 0.8
    color: str | None = None
    explanation: str | None = None
    limeWords: list[str] = Field(default_factory=list)


class ExtensionScanIn(BaseModel):
    url: str
    title: str = ""
    detections: list[ExtensionFindingIn] = Field(default_factory=list)


CATEGORY_MAP = {
    "urgency or scarcity": "false_urgency",
    "urgency": "false_urgency",
    "scarcity": "fake_scarcity",
    "confirmshaming": "confirmshaming",
    "hidden costs": "drip_pricing",
    "trick questions": "interface_interference",
    "roach motel": "obstruction",
    "disguised ads": "interface_interference",
    "misdirection": "interface_interference",
}

SEVERITY_MAP = {
    "false_urgency": 0.75,
    "fake_scarcity": 0.75,
    "confirmshaming": 0.8,
    "drip_pricing": 0.9,
    "interface_interference": 0.8,
    "obstruction": 0.9,
    "hidden_information": 0.8,
}


@app.post("/api/cases/from_extension")
def create_case_from_extension(body: ExtensionScanIn):
    cid = datetime.now().strftime("%y%m%d") + "-ext-" + uuid.uuid4().hex[:4]
    d = config.CASES_DIR / cid
    d.mkdir(parents=True, exist_ok=True)

    findings = []
    for i, det in enumerate(body.detections, 1):
        cat_key = det.category.strip().lower()
        pat = CATEGORY_MAP.get(cat_key, "interface_interference")
        sev = SEVERITY_MAP.get(pat, det.severity or 0.8)
        meta = PATTERNS.get(pat, {})
        evidence = [f'Flagged text: "{det.text}"']
        if det.limeWords:
            evidence.append(f'Key manipulative tokens (LIME): {", ".join(det.limeWords)}')
        findings.append({
            "id": f"E{i:02d}",
            "pattern": pat,
            "name": meta.get("name", pattern_name(pat)),
            "confidence": round(float(det.confidence), 2),
            "severity": sev,
            "description": det.explanation or meta.get("charge", f"Detected {det.category} pattern via DistilBERT."),
            "evidence": evidence,
            "source": "distilbert_onnx_extension",
            "step": 0,
            "url": body.url,
            "node_id": "n0"
        })

    charges = build_charges(findings)
    verdict = final_verdict(charges)

    journeys = [{
        "goal": "realtime_browser_audit",
        "label": f"Live Browser Audit ({body.title or body.url})",
        "reached": True,
        "clicks": 1,
        "path": ["n0"],
        "steps": [
            {
                "step": 0,
                "node_id": "n0",
                "url": body.url,
                "title": body.title or body.url,
                "testimony": f'User audited live web page "{body.title or body.url}". Offline DistilBERT ML model scanned active DOM elements.',
                "observations": [f"{f['name']}: {f['evidence'][0]}" for f in findings[:6]],
                "screenshot": None
            },
            {
                "step": 1,
                "node_id": None,
                "testimony": f"Page scan complete. {len(findings)} deceptive patterns flagged with high confidence.",
                "observations": [],
                "url": None,
                "title": None,
                "screenshot": None
            }
        ],
        "alternatives": []
    }]

    case = {
        "id": cid,
        "url": body.url,
        "goals": ["realtime_scan"],
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "findings": findings,
        "charges": charges,
        "journeys": journeys,
        "trees": {},
        "verdict": verdict,
        "source": "chrome_extension_distilbert",
        "log": [f"Scanned {len(body.detections)} dark patterns using in-browser DistilBERT model on {body.url}"]
    }

    save_case(case)
    report.write_html(case, d / "report.html")
    report.write_pdf(case, d / "report.pdf")

    return {
        "id": cid,
        "status": "complete",
        "verdict": verdict,
        "charges_count": len(charges),
        "findings_count": len(findings),
        "report_pdf_url": f"/api/cases/{cid}/files/report.pdf",
        "report_html_url": f"/api/cases/{cid}/files/report.html"
    }


@app.get("/api/cases")
def list_cases():
    out = []
    if not config.CASES_DIR.exists():
        return out
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
