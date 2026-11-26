"""Correction through the same field.

Two sentences still write one owns fact.
Dax tails go from blue to green. Mira's answer changes.
Owns stays.
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

def example_for(order):
    out = []
    for s, r, o in [("ada", "vek", "box"), ("ned", "vek", "key")]:
        roles = {"s": s, "r": r, "o": o}
        out.append((" ".join(roles[role] for role in order), (s, "owns", o)))
    return out

def color(field, name, objects):
    kind = ask(field, name, "isa", objects)
    if not kind:
        return None
    return ask(field, kind, "tail", objects)

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
    other = {"order": ["s", "r", "o"], "rel_at": 1, "word": "vek", "meaning": "holds"}
    library = [c for c in (vek, owns, isa) if c]
    save(FIELD, library)
    loaded = load(FIELD)
    objects = ["isa", "tail", "hastail", "blue", "green", "dax"]
    field = []
    for sent in ("rex owns map", "map vek rex", "mira isa dax"):
        fact = select(loaded, sent)
        if fact and fact not in [(f["s"], f["r"], f["o"]) for f in field]:
            for t in fact:
                if t not in objects:
                    objects.append(t)
            add(field, *fact)
    add(field, "dax", "tail", "blue")
    before = color(field, "mira", objects)
    field = [f for f in field if not (f["s"] == "dax" and f["r"] == "tail")]
    add(field, "dax", "tail", "green")
    after = color(field, "mira", objects)
    checks = {
        "all_six_applied": all(applied.values()) and len(applied) == 6,
        "one_fact": sum(1 for f in field if f["s"] == "rex" and f["r"] == "owns") == 1,
        "before_blue": before == "blue",
        "after_green": after == "green",
        "owns_kept": ask(field, "rex", "owns", objects) == "map",
        "real_clash": select([vek, other], "map vek rex") is None if vek else False,
        "unknown_abstain": select(loaded, "rex holds map") is None,
        "library_reloaded": len(loaded) == 3,
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {**checks, "failed": failed, "claim": "correction changes the derived answer; owns stays"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/roles_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
