"""Central configuration. Every value can be overridden with an environment variable."""
import os
from pathlib import Path

# Load .env from the project root (repo root / backend/) automatically.
# python-dotenv is already a transitive dependency of uvicorn[standard].
try:
    from dotenv import load_dotenv
    _here = Path(__file__).resolve().parent  # backend/app/
    for _candidate in [_here.parent.parent / ".env",   # repo root  ← your file
                       _here.parent / ".env",           # backend/
                       _here / ".env"]:                 # backend/app/
        if _candidate.exists():
            load_dotenv(_candidate, override=False)     # override=False: real env vars win
            break
except ImportError:
    pass  # dotenv not installed — rely on shell env vars

BASE_DIR = Path(__file__).resolve().parent.parent          # backend/
PROJECT_DIR = BASE_DIR.parent                               # repo root
DATA_DIR = Path(os.getenv("DPC_DATA_DIR", BASE_DIR / "data"))
CASES_DIR = DATA_DIR / "cases"
SAMPLES_DIR = Path(os.getenv("DPC_SAMPLES_DIR", PROJECT_DIR / "sample_sites"))
FRONTEND_DIST = Path(os.getenv("DPC_FRONTEND_DIST", PROJECT_DIR / "frontend" / "dist"))
KB_PATH = Path(__file__).resolve().parent / "rag" / "guidelines.json"

# Browser agent
CHROMIUM_PATH = os.getenv("CHROMIUM_PATH") or None        # use Playwright's bundled Chromium when empty
HEADLESS = os.getenv("DPC_HEADLESS", "1") != "0"
VIEWPORT = {"width": int(os.getenv("DPC_VIEWPORT_W", 1280)), "height": int(os.getenv("DPC_VIEWPORT_H", 800))}
NAV_TIMEOUT_MS = int(os.getenv("DPC_NAV_TIMEOUT_MS", 30000))
SETTLE_MS = int(os.getenv("DPC_SETTLE_MS", 1200))
AUTO_DISMISS_OVERLAYS = os.getenv("DPC_AUTO_DISMISS_OVERLAYS", "1") != "0"
STEALTH_ENABLED = os.getenv("DPC_STEALTH", "1") != "0"

# Tree-of-Thought search defaults
DEFAULT_MAX_DEPTH = int(os.getenv("DPC_MAX_DEPTH", 6))
DEFAULT_BEAM_WIDTH = int(os.getenv("DPC_BEAM_WIDTH", 2))
DEFAULT_BRANCHING = int(os.getenv("DPC_BRANCHING", 3))
MAX_NODES = int(os.getenv("DPC_MAX_NODES", 40))

# Optional multimodal LLM (any OpenAI-compatible /chat/completions endpoint)
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_ENABLED = bool(LLM_API_KEY) and os.getenv("DPC_DISABLE_LLM", "0") != "1"

# OCR
OCR_ENABLED = os.getenv("DPC_DISABLE_OCR", "0") != "1"

CASES_DIR.mkdir(parents=True, exist_ok=True)
