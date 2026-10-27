# ⚖️ DarkPattern Court
### An Agentic UX Forensics System for Evidence-Based Detection of Manipulative Interfaces

> An autonomous UX-forensics agent that browses digital interfaces, detects manipulative design patterns, simulates different user decision paths, and produces courtroom-style evidence cards showing how the interface tricks, delays, pressures or misleads users.

A typical website checker says "dark pattern detected". DarkPattern Court files a **case**: it simulates a user goal (e.g. *cancel my subscription*), records the journey as **testimony**, attaches annotated screenshots as **exhibits**, cites the relevant **authority** (FTC guidance, ROSCA, India's CCPA 2023 guidelines, EU DSA/GDPR) through RAG, and returns a **verdict**:

```
Step 0: User opened "Your Account — StreamFlix" intending to: Cancel subscription.
    ⚠ Hidden Material Information: "...you will be charged ₹649/month automatically..." (10px, contrast 1.8:1)
Step 1: User clicked "Manage membership". The control was hidden below the fold (y=1332px).
Step 2: User clicked "Cancel membership" → "Tell us why"
Step 3: User clicked "Continue to cancel" → "Special offer just for you"
    ⚠ Confirmshaming: Decline control reads: "No thanks, I prefer paying full price"
Step 4: User clicked "No thanks, I prefer paying full price" → "Are you sure?"
Step 5: User clicked "Confirm cancellation" → "Cancelled"
VERDICT: GUILTY — Obstruction / Roach Motel + Subscription Trap / Forced Continuity + ...
Manipulation score: 86/100 (grade F)
```

## Features

| Component | Implementation |
|---|---|
| Playwright browser agent | `backend/app/agent/browser.py` — real Chromium, action replay, full-page screenshots |
| UI component detector | `agent/snapshot.js` extracts every control/text block with computed styles, bbox, contrast, overlays; `detectors/page_detectors.py` (14 pattern detectors) |
| Tree-of-Thought route exploration | `agent/tot_explorer.py` — beam search over page states; each candidate action is a scored "thought"; pruned alternatives are kept as evidence |
| Forensic temporal test | countdown timers & "N people viewing" counters are re-read after a reload — timers that restart are proven fake |
| Path-level detectors | `detectors/path_detectors.py` — drip pricing across checkout steps, obstruction (clicks vs fair baseline, retention screens), nagging |
| Screenshot + OCR pipeline | `vision/ocr.py` (Tesseract) — finds text that is rendered but absent from the DOM |
| Multimodal LLM witness | `vision/vlm.py` — any OpenAI-compatible vision model; also an LLM value function for ToT (optional) |
| FTC guideline RAG | `rag/guidelines.json` + dependency-free BM25 retriever `rag/retriever.py` |
| Court & evidence cards | `court/verdict.py`, `court/exhibits.py`, `report.py` → annotated exhibit PNGs, HTML court record, PDF evidence cards |
| React dashboard | `frontend/` — new case, docket, verdict gauge, evidence cards, testimony timeline, interactive thought tree |
| Sample dark-pattern sites | `sample_sites/` — ShopKart, StreamFlix, NewsDaily, Mailer + a fair control site |

Detected patterns: false urgency, fake scarcity, fake social proof, pre-selected consent, basket sneaking, drip pricing / hidden fees, confirmshaming, interface interference (asymmetric choice), hidden material information, forced continuity / subscription trap, obstruction / roach motel, nagging, trick question, forced action.

## Quick start (≈5 minutes)

Requirements: Python 3.10+, (optional) Node 18+ to rebuild the dashboard, (optional) Tesseract for OCR.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium                            # downloads the browser once
uvicorn app.main:app --port 8000
```
Open **http://localhost:8000** — the pre-built React dashboard is served by the API. Click a sample interface, choose goals and press **Open investigation**.

### Command line
```bash
cd backend
python -m app.cli http://localhost:8000/samples/subscription/account.html --goal cancel_subscription
python -m app.cli http://localhost:8000/samples/shop/product.html --goal checkout
python -m app.cli http://localhost:8000/samples/consent/index.html --goal reject_cookies
```
Reports are written to `backend/data/cases/<case-id>/` (`case.json`, `report.html`, `report.pdf`, `shots/`, `exhibits/`).

### Dashboard development
```bash
cd frontend && npm install && npm run dev      # http://localhost:5173 (proxies /api to :8000)
npm run build                                  # rebuilds frontend/dist served by FastAPI
```

### Docker
```bash
docker compose up --build      # http://localhost:8000
```

### Optional AI components
```bash
export LLM_API_KEY=sk-...                 # enables the vision-LLM witness + LLM ToT value function
export LLM_BASE_URL=https://api.openai.com/v1   # any OpenAI-compatible endpoint (Groq, OpenRouter, Ollama ...)
export LLM_MODEL=gpt-4o-mini
sudo apt install tesseract-ocr            # enables OCR (macOS: brew install tesseract)
```
Without them the system runs fully offline with deterministic, explainable detectors.

### Tests
```bash
cd backend
pytest -m "not e2e"     # fast unit tests (synthetic snapshots)
pytest -m e2e           # audits every sample site in a real browser
```

## Configuration
All settings are environment variables (see `backend/app/config.py`): `CHROMIUM_PATH`, `DPC_HEADLESS=0` (watch the agent), `DPC_MAX_DEPTH`, `DPC_BEAM_WIDTH`, `DPC_BRANCHING`, `DPC_MAX_NODES`, `DPC_DISABLE_OCR`, `DPC_DISABLE_LLM`.

## Repository layout
```
backend/app/        FastAPI app, agent, detectors, vision, RAG, court, reports
backend/tests/      unit + end-to-end tests
frontend/           React (Vite) dashboard; dist/ is pre-built
sample_sites/       demo interfaces with deliberate dark patterns + fair control
docs/               architecture, methodology, evaluation plan, report outline, example output
```

## Ethics & scope
Audit only sites you own or are permitted to test; respect robots/terms of service. Findings are automated evidence for expert review — **not legal advice**. Guideline passages in the knowledge base are paraphrased summaries; verify against the original sources before citing them formally.
