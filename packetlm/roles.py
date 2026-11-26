"""No private color function.

The answer is the stored operator: isa chain tail, isa compose hastail.
Remove the operator. The answer must die.
Each sentence is checked before the facts are merged.
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
    meanings = {r for _, (_, r, _) in examples}
    if len(meanings) != 1:
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
    if ask(field, "isa", "compose", objects) != "hastail":
        return None
    if ask(field, "isa", "chain", objects) != "tail":
        return None
    kind = ask(field, name, "isa", objects)
    if not kind:
        return None
    return ask(field, kind, "tail", objects)

def run() -> dict:
    vek = induce([
        ("box vek ada", ("ada", "owns", "box")),
        ("key vek ned", ("ned", "owns", "key")),
    ])
    owns = induce([
        ("ada owns box", ("ada", "owns", "box")),
        ("ned owns key", ("ned", "owns", "key")),
    ])
    bad = induce([
        ("ada vek box", ("ada", "owns", "box")),
        ("ned vek key", ("ned", "holds", "key")),
    ])
    isa = induce([
        ("mira isa dax", ("mira", "isa", "dax")),
        ("sam isa cat", ("sam", "isa", "cat")),
    ])
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
    with_op = through_operator(field, "mira", objects)
    stripped = [f for f in field if f["r"] != "compose"]
    without_op = through_operator(stripped, "mira", objects)
    checks = {
        "each_sentence": owns_sent == ("rex", "owns", "map") and vek_sent == ("rex", "owns", "map"),
        "one_fact": sum(1 for f in field if f["s"] == "rex" and f["r"] == "owns") == 1,
        "through_operator": with_op == "green",
        "operator_causal": without_op is None,
        "contradiction_rejected": bad is None,
        "unknown_abstain": select(loaded, "rex holds map") is None,
        "library_reloaded": len(loaded) == 3,
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "failed": failed,
        "claim": "answer dies when the operator is removed; no private color function"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/roles_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
