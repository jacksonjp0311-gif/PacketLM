"""Suite held together.

Six orders applied.
Operator answers. Remove it and the answer dies.
Contradictory labels rejected.
Not a general mind.
"""

from __future__ import annotations
import json
from itertools import permutations
from pathlib import Path
from .field import add, ask, save, load

ORDERS = list(permutations(["s", "r", "o"]))
FIELD = Path("data/roles_field.json")

def fits(order, examples) -> bool:
    for sent, (s, r, o) in examples:
        parts = sent.lower().split()
        if len(parts) != 3:
            return False
        mapped = {role: parts[i] for i, role in enumerate(order)}
        if (mapped["s"], mapped["o"]) != (s, o):
            return False
    return True

def induce(examples):
    if len(examples) < 2:
        return None
    if len({r for _, (_, r, _) in examples}) != 1:
        return None
    hits = [order for order in ORDERS if fits(order, examples)]
    if len(hits) != 1:
        return None
    order = hits[0]
    rel_at = order.index("r")
    return {
        "order": list(order),
        "rel_at": rel_at,
        "word": examples[0][0].split()[rel_at],
        "meaning": examples[0][1][1],
    }

def select(library, sentence):
    parts = sentence.lower().strip().split()
    if len(parts) != 3:
        return None
    hits = [c for c in library if parts[c["rel_at"]] == c["word"]]
    if len(hits) != 1:
        return None
    c = hits[0]
    mapped = {role: parts[i] for i, role in enumerate(c["order"])}
    return mapped["s"], c["meaning"], mapped["o"]

def through_operator(field, name, objects):
    if ask(field, "isa", "compose", objects) != "hastail" or ask(field, "isa", "chain", objects) != "tail":
        return None
    kind = ask(field, name, "isa", objects)
    return ask(field, kind, "tail", objects) if kind else None

def example_for(order):
    out = []
    for s, r, o in [("ada", "vek", "box"), ("ned", "vek", "key")]:
        roles = {"s": s, "r": r, "o": o}
        out.append((" ".join(roles[role] for role in order), (s, "owns", o)))
    return out

def run() -> dict:
    applied = {}
    for order in ORDERS:
        got = induce(example_for(order))
        roles = {"s": "rex", "r": "vek", "o": "map"}
        sent = " ".join(roles[role] for role in order)
        applied["".join(order)] = select([got], sent) == ("rex", "owns", "map") if got else False
    vek = induce(example_for(("o", "r", "s")))
    owns = induce([("ada owns box", ("ada", "owns", "box")), ("ned owns key", ("ned", "owns", "key"))])
    isa = induce([("mira isa dax", ("mira", "isa", "dax")), ("sam isa cat", ("sam", "isa", "cat"))])
    bad = induce([("ada vek box", ("ada", "owns", "box")), ("ned vek key", ("ned", "holds", "key"))])
    library = [c for c in (vek, owns, isa) if c]
    save(FIELD, library)
    loaded = load(FIELD)
    owns_sent = select(loaded, "rex owns map")
    vek_sent = select(loaded, "map vek rex")
    objects = ["isa", "tail", "hastail", "green", "dax"]
    field = []
    for fact in (owns_sent, vek_sent, select(loaded, "mira isa dax")):
        if fact and fact not in [(f["s"], f["r"], f["o"]) for f in field]:
            for t in fact:
                if t not in objects:
                    objects.append(t)
            add(field, *fact)
    add(field, "isa", "chain", "tail")
    add(field, "isa", "compose", "hastail")
    add(field, "dax", "tail", "green")
    checks = {
        "all_six_applied": all(applied.values()) and len(applied) == 6,
        "each_sentence": owns_sent == vek_sent == ("rex", "owns", "map"),
        "through_operator": through_operator(field, "mira", objects) == "green",
        "operator_causal": through_operator([f for f in field if f["r"] != "compose"], "mira", objects) is None,
        "contradiction_rejected": bad is None,
        "unknown_abstain": select(loaded, "rex holds map") is None,
        "library_reloaded": len(loaded) == 3,
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {**checks, "failed": failed, "claim": "six orders and operator causality in one run"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/roles_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
