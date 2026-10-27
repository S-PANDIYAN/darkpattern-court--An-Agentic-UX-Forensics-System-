"""Dark-pattern taxonomy used by the detectors, the court and the RAG retriever.

Categories follow the FTC staff report "Bringing Dark Patterns to Light" (2022):
  1. Design elements that induce false beliefs
  2. Design elements that hide or delay disclosure of material information
  3. Design elements that lead to unauthorized charges
  4. Design elements that obscure or subvert privacy choices
The `india_ccpa` field maps each pattern to the closest term in India's CCPA
"Guidelines for Prevention and Regulation of Dark Patterns, 2023".
"""

PATTERNS = {
    "false_urgency": dict(
        name="False Urgency", category="Induce false beliefs", india_ccpa="False Urgency",
        charge="Fabricating time pressure (countdown timers / limited-time claims) to rush the user.",
        query="fake countdown timer false urgency limited time offer pressure"),
    "fake_scarcity": dict(
        name="Fake Scarcity", category="Induce false beliefs", india_ccpa="False Urgency",
        charge="Claiming low stock or high demand to pressure the purchase decision.",
        query="low stock scarcity claim only few left false"),
    "fake_social_proof": dict(
        name="Fake Social Proof", category="Induce false beliefs", india_ccpa="False Urgency",
        charge="Showing activity messages (\"23 people are viewing\") that appear fabricated.",
        query="fake social proof activity notifications people viewing testimonials"),
    "preselected_consent": dict(
        name="Pre-selected Consent", category="Obscure or subvert privacy choices", india_ccpa="Forced Action / Interface Interference",
        charge="Opting the user in by default to data sharing, marketing or tracking.",
        query="pre-checked box default consent privacy data sharing marketing opt-in"),
    "basket_sneaking": dict(
        name="Basket Sneaking", category="Lead to unauthorized charges", india_ccpa="Basket Sneaking",
        charge="Adding paid items (insurance, donations, add-ons) to the order without an explicit choice.",
        query="sneaking items into basket pre-checked add-on insurance donation unauthorized charge"),
    "drip_pricing": dict(
        name="Drip Pricing / Hidden Fees", category="Hide or delay material information", india_ccpa="Drip Pricing",
        charge="Revealing mandatory fees only late in the checkout, after the advertised price.",
        query="drip pricing hidden fees mandatory fees disclosed late total price"),
    "confirmshaming": dict(
        name="Confirmshaming", category="Induce false beliefs", india_ccpa="Confirm Shaming",
        charge="Wording the decline option to guilt or shame the user into accepting.",
        query="confirmshaming guilt shame decline option wording"),
    "interface_interference": dict(
        name="Interface Interference (Asymmetric Choice)", category="Obscure or subvert privacy choices", india_ccpa="Interface Interference",
        charge="Making the option that benefits the business visually dominant while the alternative is hidden or de-emphasised.",
        query="accept all prominent reject hidden asymmetric choice visual interference"),
    "hidden_information": dict(
        name="Hidden Material Information", category="Hide or delay material information", india_ccpa="Interface Interference",
        charge="Placing material terms (renewal, fees, cancellation) in tiny or low-contrast text.",
        query="material terms fine print small text low contrast disclosure clear and conspicuous"),
    "forced_continuity": dict(
        name="Subscription Trap / Forced Continuity", category="Lead to unauthorized charges", india_ccpa="Subscription Trap",
        charge="Converting a free trial into a paid, auto-renewing plan without clear, conspicuous disclosure.",
        query="free trial automatic renewal negative option forced continuity consent ROSCA"),
    "obstruction": dict(
        name="Obstruction / Roach Motel", category="Lead to unauthorized charges", india_ccpa="Subscription Trap",
        charge="Making cancellation, rejection or unsubscribing much harder than signing up.",
        query="hard to cancel subscription obstruction roach motel simple cancellation mechanism"),
    "nagging": dict(
        name="Nagging", category="Induce false beliefs", india_ccpa="Nagging",
        charge="Repeatedly interrupting the user with pop-ups or requests.",
        query="nagging repeated pop-ups interruptions requests"),
    "trick_question": dict(
        name="Trick Question", category="Obscure or subvert privacy choices", india_ccpa="Trick Question",
        charge="Using confusing or double-negative wording so the user picks an unintended option.",
        query="trick question confusing double negative wording checkbox"),
    "forced_action": dict(
        name="Forced Action", category="Obscure or subvert privacy choices", india_ccpa="Forced Action",
        charge="Requiring an unrelated action (account creation, data sharing) to access the service.",
        query="forced action require account registration share data to continue"),
}


def pattern_name(key: str) -> str:
    return PATTERNS.get(key, {}).get("name", key)
