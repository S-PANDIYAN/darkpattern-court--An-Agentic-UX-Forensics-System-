"""End-to-end: audits the bundled sample sites in a real browser. Skipped if Playwright/Chromium is unavailable.
Run:  pytest -m e2e   (starts a local static server automatically)"""
import functools, http.server, threading, uuid
import pytest
from app import config
from app.audit import run_audit

pytestmark = pytest.mark.e2e

CASES = [
    ("subscription/account.html", ["cancel_subscription"], {"obstruction", "forced_continuity"}, "GUILTY"),
    ("consent/index.html", ["reject_cookies"], {"interface_interference", "preselected_consent"}, "GUILTY"),
    ("shop/product.html", ["checkout"], {"drip_pricing", "basket_sneaking", "false_urgency"}, "GUILTY"),
    ("newsletter/unsubscribe.html", ["unsubscribe"], {"trick_question"}, None),
    ("fair/index.html", ["checkout", "reject_cookies"], set(), "ACQUITTED"),
]


@pytest.fixture(scope="module")
def server():
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(config.SAMPLES_DIR))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


@pytest.mark.parametrize("path,goals,expected,verdict", CASES)
def test_sample(server, path, goals, expected, verdict):
    pytest.importorskip("playwright")
    case = run_audit({"id": "test-" + uuid.uuid4().hex[:6], "url": f"{server}/{path}", "goals": goals, "max_depth": 6})
    if case["status"] == "error" and "Executable doesn't exist" in case.get("error", ""):
        pytest.skip("Chromium not installed (run: playwright install chromium)")
    assert case["status"] == "complete", case.get("error")
    found = {c["pattern"] for c in case["charges"] if c["verdict"] in ("GUILTY", "LIKELY")}
    assert expected <= found
    if verdict:
        assert case["verdict"]["label"] == verdict
    assert all(j["reached"] for j in case["journeys"])
