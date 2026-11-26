"""Library persists. Selection writes the field.

Reload, select, write. Unknown still abstains.
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
    return {"order": list(order), "rel_at": rel_at, "word": word}

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
    library = [
        induce([("ada owns box", ("ada", "owns", "box")), ("ned owns key", ("ned", "owns", "key"))]),
        induce([("box vek ada", ("ada", "vek", "box")), ("key vek ned", ("ned", "vek", "key"))]),
    ]
    library = [c for c in library if c]
    save(FIELD, library)
    loaded = load(FIELD)
    objects = []
    field = []
    chosen = select(loaded, "rex owns map")
    if chosen:
        for t in chosen:
            if t not in objects:
                objects.append(t)
        add(field, *chosen)
    unknown = select(loaded, "rex holds map")
    save(Path("data/roles_facts.json"), field)
    facts = load(Path("data/roles_facts.json"))
    checks = {
        "library_reloaded": len(loaded) == 2,
        "wrote_owns": chosen == ("rex", "owns", "map") and ask(facts, "rex", "owns", objects) == "map",
        "unknown_abstain": unknown is None,
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {**checks, "failed": failed, "claim": "library reloaded; selected fact written to the field"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/roles_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
