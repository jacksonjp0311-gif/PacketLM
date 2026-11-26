"""All six role orders.

Each order is induced from two examples and applied to one unseen sentence.
Two competing orders abstain.
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
    parts = sentence.lower().strip().split()
    if len(parts) != 3:
        return None
    mapped = {role: parts[i] for i, role in enumerate(order)}
    return mapped["s"], mapped["r"], mapped["o"]

def example_for(order):
    """Build two sentences whose tokens sit in this order."""
    triples = [("ada", "vek", "box"), ("ned", "vek", "key")]
    out = []
    for s, r, o in triples:
        roles = {"s": s, "r": r, "o": o}
        sent = " ".join(roles[role] for role in order)
        out.append((sent, (s, r, o)))
    return out

def run() -> dict:
    found = {}
    applied = {}
    for order in ORDERS:
        examples = example_for(order)
        got = induce(examples)
        found["".join(order)] = got == order
        # unseen uses new entities in the same order
        roles = {"s": "rex", "r": "vek", "o": "map"}
        sent = " ".join(roles[role] for role in order)
        applied["".join(order)] = apply(got, sent) == ("rex", "vek", "map")
    # ambiguous: two examples that fit more than one reading should not happen
    # with consistent labels; a single example must abstain
    one = induce([("box vek ada", ("ada", "vek", "box"))])
    checks = {
        "all_six": all(found.values()) and len(found) == 6,
        "all_applied": all(applied.values()),
        "one_example_abstains": one is None,
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "found": found,
        "failed": failed,
        "claim": "six orders induced from examples; one example abstains"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/roles_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
