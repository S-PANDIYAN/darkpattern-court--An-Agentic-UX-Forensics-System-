"""Unit tests on synthetic UI snapshots (no browser needed)."""
from app.utils import contrast_ratio, prices
from app.detectors.page_detectors import run_page_detectors
from app.detectors import path_detectors as PD
from app.agent.goals import GOALS
from app.court.verdict import build_charges, final_verdict
from app.rag.retriever import retrieve


def el(text, tag="button", checked=None, w=200, h=50, color="rgb(255, 255, 255)", bg="rgb(37, 99, 235)", own=None, fs=16, y=100):
    return {"id": "0", "tag": tag, "type": "checkbox" if checked is not None else "", "role": "", "text": text, "href": "", "abs": "",
            "checked": checked, "disabled": False, "visible": True, "bbox": {"x": 10, "y": y, "w": w, "h": h}, "color": color, "bg": bg,
            "ownBg": own if own is not None else bg, "fontSize": fs, "fontWeight": 700, "sameOrigin": True}


def txt(t, fs=14, color="rgb(17, 24, 39)", bg="rgb(255, 255, 255)"):
    return {"text": t, "tag": "p", "fontSize": fs, "color": color, "bg": bg, "bbox": {"x": 0, "y": 0, "w": 300, "h": 20}}


def snap(elements=(), texts=(), text=None, overlays=()):
    texts = list(texts)
    return {"url": "http://t/x", "title": "T", "viewport": {"w": 1280, "h": 800}, "scrollHeight": 900,
            "text": text if text is not None else " ".join(t["text"] for t in texts) + " " + " ".join(e["text"] for e in elements),
            "elements": list(elements), "texts": texts, "overlays": list(overlays)}


def patterns(s, ctx=None):
    return {f.pattern for f in run_page_detectors(s, ctx or {})}


def test_contrast():
    assert contrast_ratio("rgb(0,0,0)", "rgb(255,255,255)") == 21.0
    assert contrast_ratio("rgb(200,200,200)", "rgb(255,255,255)") < 2


def test_prices():
    assert prices("Total ₹3,021 and $19.99") == [3021.0, 19.99]


def test_preselected_and_sneaking():
    s = snap([el("Send me marketing emails from partners", "input", True), el("Add protection plan (+₹399)", "input", True)])
    p = patterns(s)
    assert "preselected_consent" in p and "basket_sneaking" in p


def test_unchecked_is_fair():
    assert not patterns(snap([el("Email me offers", "input", False)]))


def test_confirmshaming():
    assert "confirmshaming" in patterns(snap([el("No thanks, I don't like saving money", "a")]))


def test_asymmetric_cookie_banner():
    acc = el("Accept all", w=220, h=56)
    rej = el("Manage options", "a", w=90, h=14, color="rgb(170, 170, 170)", bg="rgb(255, 255, 255)", own="rgba(0, 0, 0, 0)", fs=12)
    s = snap([acc, rej], [txt("We use cookies for advertising")])
    assert "interface_interference" in patterns(s)


def test_symmetric_banner_is_fair():
    s = snap([el("Accept all"), el("Reject all")], [txt("We use cookies")])
    assert "interface_interference" not in patterns(s)


def test_fake_timer_reset():
    s = snap(texts=[txt("Deal ends in 09:58 — hurry!")])
    f = [x for x in run_page_detectors(s, {"probe": {"timers_before": [598], "timers_after": [599], "elapsed_s": 2}}) if x.pattern == "false_urgency"]
    assert f and f[0].confidence >= 0.9 and f[0].source == "temporal"


def test_forced_continuity_hidden():
    s = snap(texts=[txt("Start your free trial today"), txt("Auto-renews at ₹649/month, you will be charged automatically", fs=9, color="rgb(200,200,200)")])
    p = patterns(s)
    assert "forced_continuity" in p and "hidden_information" in p


def test_trick_question():
    assert "trick_question" in patterns(snap(texts=[txt("Uncheck this box if you do not want to not receive offers")]))


def node(i, text, title="p", action=None):
    return {"id": f"n{i}", "depth": i, "url": f"http://t/{i}", "action": action or {"text": f"a{i}", "bbox": {"y": 10}},
            "snapshot": {"text": text, "title": title, "overlays": []}}


def test_drip_pricing():
    path = [node(0, "Headphones ₹2,499"), node(1, "Cart ₹2,499"), node(2, "Item ₹2,499\nConvenience fee ₹49\nTotal ₹2,548")]
    f = PD.drip_pricing(path)
    assert f and f[0].pattern == "drip_pricing"


def test_obstruction():
    path = [node(0, "account"), node(1, "membership"), node(2, "Wait! 50% off before you go"), node(3, "Are you sure?"), node(4, "cancelled")]
    f = PD.obstruction(path, GOALS["cancel_subscription"], True, 6)
    assert f and f[0].confidence > 0.8


def test_court_and_rag():
    fs = [{"pattern": "obstruction", "confidence": .9, "severity": .8, "source": "path", "url": "u", "evidence": ["x"], "description": "d"},
          {"pattern": "confirmshaming", "confidence": .5, "severity": .5, "source": "dom", "url": "u", "evidence": ["y"], "description": "d"}]
    ch = build_charges(fs)
    assert ch[0]["verdict"] == "GUILTY" and ch[0]["authorities"]
    assert final_verdict(ch)["label"] == "GUILTY"
    assert any("rosca" == d["id"] or "click" in d["id"] for d in retrieve("obstruction"))
