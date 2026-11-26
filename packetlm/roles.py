"""Role induction.

Six permutations. The examples pick the order.
If more than one order fits, abstain.
Not a general mind.
"""

from __future__ import annotations
import json
from itertools import permutations
from pathlib import Path

ORDERS = list(permutations(["s", "r", "o"]))

def fits(order, examples) -> bool:
    for sent, (s, r, o) in examples:
        parts = sent.lower().split()
        if len(parts) != 3:
            return False
        mapped = {role: parts[i] for i, role in enumerate(order)}
        if mapped != {"s": s, "r": r, "o": o}:
            return False
    return True

def induce(examples):
    if len(examples) < 2:
        return None
    hits = [order for order in ORDERS if fits(order, examples)]
    if len(hits) != 1:
        return None
    return hits[0]

def apply(order, sentence):
    if not order:
        return None
    parts = sentence.lower().strip().rstrip(".").split()
    if len(parts) != 3:
        return None
    mapped = {role: parts[i] for i, role in enumerate(order)}
    return mapped["s"], mapped["r"], mapped["o"]

def run() -> dict:
    # O R S: box vek ada = owns(ada, box)
    ors = [
        ("box vek ada", ("ada", "vek", "box")),
        ("key vek ned", ("ned", "vek", "key")),
    ]
    # S R O
    sro = [
        ("ada owns box", ("ada", "owns", "box")),
        ("ned owns key", ("ned", "owns", "key")),
    ]
    # ambiguous: one example is not enough, two identical orders only
    order_ors = induce(ors)
    order_sro = induce(sro)
    unseen = apply(order_ors, "map vek rex")
    wrong = apply(order_ors, "rex vek map")
    checks = {
        "found_ors": order_ors == ("o", "r", "s"),
        "found_sro": order_sro == ("s", "r", "o"),
        "unseen": unseen == ("rex", "vek", "map"),
        "different_order": wrong != ("rex", "vek", "map"),
        "six_searched": len(ORDERS) == 6,
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "ors": order_ors,
        "unseen": unseen,
        "failed": failed,
        "claim": "order induced from examples; grammar was not hardcoded"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/roles_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
