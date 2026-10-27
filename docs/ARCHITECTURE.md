# Architecture

```
                ┌────────────── React dashboard (Vite) ──────────────┐
                │ new case · docket · verdict · evidence · ToT tree  │
                └───────────────▲───────────────┬────────────────────┘
                                │ REST (JSON)   │ POST /api/cases
┌───────────────────────────────┴───────────────▼────────────────────────────────┐
│ FastAPI  (app/main.py)  – case queue (thread pool), artifacts, samples, RAG API │
└───────────────────────────────┬────────────────────────────────────────────────┘
                                ▼  app/audit.py  (pipeline)
  for each user goal ─► Tree-of-Thought explorer (agent/tot_explorer.py)
        │                 propose thoughts → evaluate (heuristic ± LLM) → beam select → replay in Playwright
        ▼  every new page state (node)
  Playwright snapshot (snapshot.js) + full-page screenshot
        ├─► temporal probe (reload test for timers / counters)
        ├─► OCR (Tesseract)  → text only visible in pixels
        ├─► page detectors (14 rules over DOM + styles + OCR)
        └─► vision LLM witness (optional)
  best path + alternative paths ─► path detectors (drip pricing, obstruction, nagging)
        ▼
  Court: findings → charges (noisy-OR corroboration) → RAG authorities → verdict + score
        ▼
  Exhibits (annotated crops) · case.json · report.html · report.pdf
```

## Key design decisions
* **Evidence first.** Every finding stores the quote/measurement, page state (node), step number, URL and bounding box, so it can be rendered as an exhibit and reproduced by replaying the recorded actions.
* **State = action sequence.** Nodes are reproduced by replaying clicks from the start URL in a fresh browser context. This makes branches independent (cookies/session do not leak between simulated users) and every path reproducible.
* **Tree-of-Thought.** At each node the agent generates candidate actions, scores them against the goal (positive/negative intent lexicons, penalties for revisiting pages, optional LLM rating), keeps the top-*b* thoughts, and runs a beam of width *k* across depths. Pruned thoughts are stored with reasons → the tree itself documents which choices the interface offered.
* **Fairness baselines.** Each goal has a `fair_steps` baseline (e.g. cancel ≤ 2 clicks, reject cookies ≤ 1). Obstruction confidence grows with excess clicks and retention screens.
* **Measurable visual asymmetry.** Prominence = area × (WCAG contrast / 4.5) × weight × fill × saturation. Accept/reject ratio ≥ 3, contrast < 3:1, or reject below the fold → interface interference.
* **Corroboration.** Charge confidence = 1 − Π(1 − cᵢ) over independent witnesses (distinct source × page), mapped to GUILTY (≥ 0.8), LIKELY (≥ 0.55), INSUFFICIENT EVIDENCE.
* **Manipulation score** = min(100, Σ confidence × severity × 25) → grade A–F.
