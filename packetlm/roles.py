"""Surface word and meaning are separate.

vek maps to owns.
Two constructions that disagree on the same sentence abstain.
All six orders are induced and applied to an unseen sentence.
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
        if mapped["r"] != examples[0][0].split()[order.index("r")]:
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
    meaning = examples[0][1][1]
    return {"order": list(order), "rel_at": rel_at, "word": word, "meaning": meaning}

def select(library, sentence):
    parts = sentence.lower().strip().split()
    if len(parts) != 3:
        return None
    hits = [c for c in library if parts[c["rel_at"]] == c["word"]]
    meanings = {(c["meaning"], tuple(c["order"])) for c in hits}
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

def run() -> dict:
    applied = {}
    for order in ORDERS:
        got = induce(example_for(order))
        if not got:
            applied["".join(order)] = False
            continue
        roles = {"s": "rex", "r": "vek", "o": "map"}
        sent = " ".join(roles[role] for role in order)
        applied["".join(order)] = select([got], sent) == ("rex", "owns", "map")
    vek = induce(example_for(("o", "r", "s")))
    owns = induce([("ada owns box", ("ada", "owns", "box")), ("ned owns key", ("ned", "owns", "key"))])
    # real clash: same sentence, two meanings
    other = {"order": ["s", "r", "o"], "rel_at": 1, "word": "vek", "meaning": "holds"}
    clash = select([vek, other], "map vek rex") if vek else None
    library = [c for c in (vek, owns) if c]
    save(FIELD, library)
    loaded = load(FIELD)
    objects = ["rex", "owns", "map"]
    field = []
    chosen = select(loaded, "map vek rex")
    if chosen:
        add(field, *chosen)
    checks = {
        "all_six_applied": all(applied.values()) and len(applied) == 6,
        "vek_means_owns": chosen == ("rex", "owns", "map") and ask(field, "rex", "owns", objects) == "map",
        "unknown_abstain": select(loaded, "rex holds map") is None,
        "real_clash": clash is None,
        "library_reloaded": len(loaded) == 2,
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "applied": applied,
        "chosen": chosen,
        "failed": failed,
        "claim": "vek means owns; six orders applied; real clash abstains"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/roles_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
