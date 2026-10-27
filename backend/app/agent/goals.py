"""User goals the agent simulates. Each goal defines how a 'thought' (candidate action) is scored
and how success is recognised. `kind` tells path detectors what is fair:
  exit    – leaving a relationship (cancel / unsubscribe): should be as easy as joining
  privacy – refusing tracking: should be as easy as accepting
  purchase – buying: price must be transparent, nothing added silently
  accept  – the 'happy path' the business wants (used as a baseline for symmetry)
"""
GOALS = {
    "cancel_subscription": dict(
        label="Cancel subscription", kind="exit", fair_steps=2,
        positive={"cancel subscription": 10, "cancel membership": 10, "cancel my": 9, "continue to cancel": 9, "confirm cancel": 10,
                  "yes, cancel": 10, "cancel": 7, "end subscription": 9, "end membership": 9, "end plan": 9, "stop renewal": 8,
                  "cancel auto-renew": 9, "turn off auto-renew": 9, "manage subscription": 6, "membership": 4,
                  "subscription": 4, "account": 3, "settings": 2, "billing": 3, "continue": 2, "submit": 2, "no, continue": 6,
                  "no thanks": 6, "no, thanks": 6, "decline": 5, "full price": 5, "i'll pass": 5, "close account": 6},
        negative={"keep": -8, "stay": -6, "accept offer": -9, "claim": -8, "resume": -6, "upgrade": -6, "go back": -5, "never mind": -6, "sign out": -4},
        success=[r"\b(subscription|membership|plan)\s+(has been\s+)?(cancel+ed|ended|terminated)\b", r"\bcancel+ation (is )?(complete|confirmed)\b",
                 r"\byou(r plan)? (have|has) been cancel+ed\b"]),
    "reject_cookies": dict(
        label="Reject non-essential cookies", kind="privacy", fair_steps=1,
        positive={"reject all": 10, "decline all": 10, "reject": 9, "decline": 8, "necessary only": 9, "only necessary": 9,
                  "essential only": 9, "only required": 9, "strictly necessary": 9, "confirm my choices": 8, ", reject": 9,
                  "save preferences": 7, "save choices": 7, "manage options": 6, "manage preferences": 7, "refuse": 8,
                  "manage": 5, "preferences": 5, "settings": 5, "customize": 5, "options": 4, "more": 1},
        negative={"accept": -9, "allow all": -9, "agree": -8, "got it": -6, "ok": -3},
        success=[r"\b(preferences|choices|settings) (have been |were )?saved\b", r"\b(non-essential )?cookies (have been )?rejected\b",
                 r"\bonly (strictly )?necessary cookies\b.*\b(active|enabled|in use)\b"]),
    "checkout": dict(
        label="Buy the product (minimal purchase)", kind="purchase", fair_steps=3,
        positive={"add to cart": 10, "buy now": 9, "checkout": 9, "proceed to checkout": 10, "proceed to pay": 9,
                  "order now": 10, "add to bag": 10, "bag": 5, "basket": 5, "view cart": 8, "pay now": 8,
                  "proceed": 7, "continue to payment": 9, "continue to checkout": 9,
                  "continue": 6, "place order": 10, "pay": 7, "review order": 7, "cart": 5, "buy": 7, "add": 4},
        negative={"protection": -6, "upgrade": -6, "donate": -6, "add insurance": -7, "wishlist": -4, "continue shopping": -7, "remove": -5},
        success=[r"\border (has been )?(placed|confirmed)\b", r"\bthank you for your (order|purchase)\b", r"\breview & pay\b", r"\bpayment (successful|confirmed)\b"]),
    "unsubscribe": dict(
        label="Unsubscribe from emails", kind="exit", fair_steps=1,
        positive={"unsubscribe from all": 10, "unsubscribe": 9, "opt out": 8, "update preferences": 6, "confirm": 6, "save": 5, "submit": 5,
                  "email preferences": 6, "continue": 3, "no thanks": 4},
        negative={"stay subscribed": -9, "keep": -7, "resubscribe": -8, "go back": -5},
        success=[r"\byou(('ve)| have)? (been )?unsubscribed\b", r"\byou will no longer receive\b", r"\bunsubscribed successfully\b"]),
    "explore": dict(
        label="Free exploration", kind="accept", fair_steps=99,
        positive={"continue": 3, "next": 3, "checkout": 3, "cart": 3, "account": 2, "settings": 2, "cancel": 2, "subscribe": 2,
                  "order": 3, "shop": 3, "deals": 3, "categories": 2, "view": 2},
        negative={}, success=[]),
}
