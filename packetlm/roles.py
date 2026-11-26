"""Correction is a sentence.

'correct dax tail green' replaces the tail.
The operator answer changes. Owns stays.
Six orders and causality stay.
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
    if len(examples) < 2 or len({r for _, (_, r, _) in examples}) != 1:
        return None
    hits = [order for order in ORDERS if fits(order, examples)]
    if len(hits) != 1:
        return None
    order = hits[0]
    rel_at = order.index("r")
    return {"order": list(order), "rel_at": rel_at, "word": examples[0][0].split()[rel_at], "meaning": examples[0][1][1]}

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

def correct(field, sentence):
    parts = sentence.lower().split()
    if len(parts) != 4 or parts[0] != "correct":
        return field
    _, s, r, o = parts
    field = [f for f in field if not (f["s"] == s and f["r"] == r)]
    add(field, s, r, o)
    return field

def example_for(order):
    return [(" ".join({"s": s, "r": r, "o": o}[role] for role in order), (s, "owns", o)) for s, r, o in [("ada", "vek", "box"), ("ned", "vek", "key")]]

def run() -> dict:
    applied = {}
    for order in ORDERS:
        got = induce(example_for(order))
        roles = {"s": "rex", "r": "vek", "o": "map"}
        applied["".join(order)] = select([got], " ".join(roles[role] for role in order)) == ("rex", "owns", "map") if got else False
    vek = induce(example_for(("o", "r", "s")))
    owns = induce([("ada owns box", ("ada", "owns", "box")), ("ned owns key", ("ned", "owns", "key"))])
    isa = induce([("mira isa dax", ("mira", "isa", "dax")), ("sam isa cat", ("sam", "isa", "cat"))])
    library = [c for c in (vek, owns, isa) if c]
    save(FIELD, library)
    loaded = load(FIELD)
    objects = ["isa", "tail", "hastail", "blue", "green", "dax"]
    field = []
    for fact in (select(loaded, "rex owns map"), select(loaded, "map vek rex"), select(loaded, "mira isa dax")):
        if fact and fact not in [(f["s"], f["r"], f["o"]) for f in field]:
            for t in fact:
                if t not in objects:
                    objects.append(t)
            add(field, *fact)
    add(field, "isa", "chain", "tail")
    add(field, "isa", "compose", "hastail")
    add(field, "dax", "tail", "blue")
    before = through_operator(field, "mira", objects)
    field = correct(field, "correct dax tail green")
    after = through_operator(field, "mira", objects)
    checks = {
        "all_six_applied": all(applied.values()) and len(applied) == 6,
        "before_blue": before == "blue",
        "corrected_green": after == "green",
        "owns_kept": ask(field, "rex", "owns", objects) == "map",
        "operator_causal": through_operator([f for f in field if f["r"] != "compose"], "mira", objects) is None,
        "unknown_abstain": select(loaded, "rex holds map") is None,
        "library_reloaded": len(loaded) == 3,
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {**checks, "failed": failed, "claim": "correction sentence revises the tail; suite retained"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/roles_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
