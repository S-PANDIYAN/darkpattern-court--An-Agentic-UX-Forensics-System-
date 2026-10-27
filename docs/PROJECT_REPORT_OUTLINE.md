# Final-Year Project Report — Outline

**Title:** DarkPattern Court: An Agentic UX Forensics System for Evidence-Based Detection of Manipulative Interfaces

**Abstract (draft).** Manipulative interface design — hard-to-cancel subscriptions, hidden fees, fake urgency, pre-selected consent and asymmetric choices — harms consumers and is increasingly targeted by regulators such as the U.S. FTC, the EU (DSA, GDPR) and India's CCPA (2023 dark-pattern guidelines). Existing detectors classify single pages and output labels without explaining *how* the user is harmed. We present DarkPattern Court, an autonomous agent that drives a real browser, simulates user goals with Tree-of-Thought route exploration, and combines DOM/visual analysis, OCR, forensic reload tests and an optional multimodal LLM to detect 14 dark-pattern types. Findings are assembled into courtroom-style evidence: step-by-step testimony, annotated exhibits and citations retrieved from a regulatory knowledge base, ending in a verdict and manipulation score. On purpose-built test interfaces the system reached every user goal, detected all seeded patterns, and acquitted a fair control site.

1. **Introduction** — problem, motivation, objectives, contributions (journey-level forensics, ToT exploration, evidence cards, regulatory RAG).
2. **Background & literature review** — Brignull's taxonomy; Gray et al. (2018); Mathur et al. (2019) *Dark Patterns at Scale*; Nouwens et al. (2020) consent pop-ups; FTC *Bringing Dark Patterns to Light* (2022); EDPB Guidelines 03/2022; India CCPA 2023; Tree of Thoughts (Yao et al., 2023); web agents (WebArena, Mind2Web); UI detection & OCR.
3. **Requirements & system design** — use cases, architecture (docs/ARCHITECTURE.md), data model (Finding, Node, Charge, Case).
4. **Implementation** — browser agent, snapshot, detectors, temporal probe, ToT, OCR/VLM, RAG, court, reports, dashboard.
5. **Testing & evaluation** — docs/METHODOLOGY_AND_EVALUATION.md; unit + e2e tests; ablations; user study.
6. **Results & discussion** — tables, example evidence cards (docs/example_output/), failure cases.
7. **Ethics, legal & social aspects** — responsible auditing, false accusations, not legal advice.
8. **Conclusion & future work** — mobile apps (Appium), multilingual lexicons, learned UI detectors (YOLO on screenshots), browser extension, longitudinal monitoring.

**Appendices:** API reference (`/docs` Swagger at http://localhost:8000/docs), test results, user-study forms.
