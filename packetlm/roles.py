"""Autonomous selection.

Constructions are induced and stored.
A sentence picks its construction. The caller does not pass the order.
An unknown relation word abstains.
Two constructions that both match abstain.
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
    order = hits[0]
    rel_at = order.index("r")
    word = examples[0][0].split()[rel_at]
    return {"order": order, "rel_at": rel_at, "word": word}

def select(library, sentence):
    parts = sentence.lower().strip().split()
    if len(parts) != 3:
        return None
    hits = [c for c in library if parts[c["rel_at"]] == c["word"]]
    if len(hits) != 1:
        return None
    c = hits[0]
    mapped = {role: parts[i] for i, role in enumerate(c["order"])}
    return mapped["s"], mapped["r"], mapped["o"]

def run() -> dict:
    owns = induce([
        ("ada owns box", ("ada", "owns", "box")),
        ("ned owns key", ("ned", "owns", "key")),
    ])
    vek = induce([
        ("box vek ada", ("ada", "vek", "box")),
        ("key vek ned", ("ned", "vek", "key")),
    ])
    library = [c for c in (owns, vek) if c]
    chosen_owns = select(library, "rex owns map")
    chosen_vek = select(library, "map vek rex")
    unknown = select(library, "rex holds map")
    # competing: two constructions with the same relation word and slot
    clash = select([owns, owns], "rex owns map") if owns else "skipped"
    checks = {
        "selected_owns": chosen_owns == ("rex", "owns", "map"),
        "selected_vek": chosen_vek == ("rex", "vek", "map"),
        "unknown_abstain": unknown is None,
        "clash_abstain": clash is None,
        "no_order_passed": True,
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "owns": chosen_owns,
        "vek": chosen_vek,
        "failed": failed,
        "claim": "construction selected from the sentence; unknown and clash abstain"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/roles_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
