# Methodology & Evaluation Plan

## Research questions
1. Can an autonomous agent reproduce the *journey-level* harm of dark patterns (obstruction, drip pricing) that single-page scanners miss?
2. Does Tree-of-Thought exploration find goal paths (e.g. cancellation) more reliably than a greedy single chain?
3. Do forensic tests (reload probe, contrast measurement, click counting) increase precision over keyword matching?

## Dataset
* **Synthetic ground truth** — `sample_sites/` (5 sites, 21 pages) with a labelled pattern list per page (extend `tests/test_e2e_samples.py`). Add more pages by varying wording, layout and CSS to avoid over-fitting the rules.
* **Real-world set** — e.g. 50 consent banners + 20 subscription cancel flows audited with permission, manually labelled by 2 annotators (report Cohen's κ). Public corpora to compare with: Mathur et al. (2019) *Dark Patterns at Scale* (11K shopping sites) and the consent-banner studies by Nouwens et al. (2020).

## Metrics
| Level | Metric |
|---|---|
| Finding | precision, recall, F1 per pattern; false-positive rate on fair control pages |
| Journey | goal success rate, clicks-to-goal, states explored, runtime |
| Exploration | ToT (beam = 2, branching = 3) vs greedy (beam = 1, branching = 1) vs BFS — success rate & nodes expanded |
| Ablations | without temporal probe · without OCR · without vision LLM · without RAG (citation relevance, judged 1–5) |
| Usability | 5-participant study: do evidence cards make findings more understandable/convincing than a plain list? (SUS + Likert) |

Run the greedy baseline: `python -m app.cli <url> --goal cancel_subscription --beam 1 --branching 1`.

## Current results on the bundled samples (no LLM, no OCR)
| Site | Goal | Reached | Clicks | Verdict | Main charges |
|---|---|---|---|---|---|
| StreamFlix | cancel subscription | ✔ | 5 | GUILTY (86) | obstruction, forced continuity, hidden info, interface interference, confirmshaming |
| ShopKart | checkout | ✔ | 3 | GUILTY (100) | basket sneaking, drip pricing, false urgency (reset timer), fake scarcity/social proof, nagging |
| NewsDaily | reject cookies | ✔ | 3 | GUILTY (53) | obstruction, interface interference, pre-selected consent, confirmshaming |
| Mailer | unsubscribe | ✔ | 2 | GUILTY (47) | interface interference, pre-selected consent, trick question, obstruction |
| FairShop (control) | checkout + reject | ✔ | 3 / 1 | ACQUITTED (0) | — |

## Limitations
Rule lexicons are English-centric; logins, CAPTCHAs and payment steps are out of scope; heavy SPAs may need longer `DPC_SETTLE_MS`; legal text is summarised, not authoritative.
