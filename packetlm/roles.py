"""Reload and answer. No retrain.

Library and facts are saved, then loaded.
The operator still answers. Owns still there.
Not a general mind.
"""

from __future__ import annotations
import json
from itertools import permutations
from pathlib import Path
from .field import add, ask, save, load

ORDERS = list(permutations(["s", "r", "o"]))
LIB = Path("data/roles_field.json")
FACTS = Path("data/roles_facts.json")

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

def run() -> dict:
    vek = induce([("box vek ada", ("ada", "owns", "box")), ("key vek ned", ("ned", "owns", "key"))])
    owns = induce([("ada owns box", ("ada", "owns", "box")), ("ned owns key", ("ned", "owns", "key"))])
    isa = induce([("mira isa dax", ("mira", "isa", "dax")), ("sam isa cat", ("sam", "isa", "cat"))])
    library = [c for c in (vek, owns, isa) if c]
    save(LIB, library)
    loaded = load(LIB)
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
    field = correct(field, "correct dax tail green")
    save(FACTS, field)
    facts = load(FACTS)
    checks = {
        "corrected_green": through_operator(facts, "mira", objects) == "green",
        "owns_kept": ask(facts, "rex", "owns", objects) == "map",
        "operator_causal": through_operator([f for f in facts if f["r"] != "compose"], "mira", objects) is None,
        "unknown_abstain": select(loaded, "rex holds map") is None,
        "reloaded_facts": len(facts) == len(field),
        "library_reloaded": len(loaded) == 3,
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {**checks, "failed": failed, "claim": "answered after reload; no retrain"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/roles_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
