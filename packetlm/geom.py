"""Library use.

The stored program is offered as a primitive.
The search is not told its name.
A later task uses it.
Not a proven advantage. Not a general mind.
"""

from __future__ import annotations
import json
from itertools import product
from pathlib import Path
from .field import save, load

STATE = Path("data/geom_state.json")

def bits(m):
    return [i for i in range(m.bit_length()) if m & (1 << i)]

def rows_from(facts, n, rel):
    rows = [0] * n
    for s, r, o in facts:
        if r == rel:
            rows[s] |= 1 << o
    return rows

def compose(a_rows, b_rows):
    out = []
    for a in a_rows:
        acc, k, row = 0, 0, a
        while row:
            if row & 1:
                acc |= b_rows[k]
            row >>= 1
            k += 1
        out.append(acc)
    return out

def run() -> dict:
    facts = [
        (0, "in", 1), (1, "in", 2), (2, "in", 5),
        (0, "near", 3), (3, "near", 4),
        (1, "near", 3), (3, "in", 4),
    ]
    rels = sorted({r for _, r, _ in facts})
    n = 6
    base = {rel: rows_from(facts, n, rel) for rel in rels}
    programs = []
    for length in (1, 2):
        for seq in product(rels, repeat=length):
            rows = base[seq[0]]
            for rel in seq[1:]:
                rows = compose(rows, base[rel])
            programs.append((seq, rows))
    preds = [bits(rows[0]) for _, rows in programs]
    supported = [i for i, pred in enumerate(preds) if set(pred) == {2}]
    undetermined = [i for i, pred in enumerate(preds) if not pred]
    qualified = len(supported) == 1 and not undetermined
    chosen = programs[supported[0]] if qualified else None
    save(STATE, {"seq": list(chosen[0]), "rows": chosen[1]} if chosen else {})
    loaded = load(STATE)
    # later search: primitives plus whatever was stored, unnamed
    library = dict(base)
    if loaded.get("rows"):
        library["acquired"] = loaded["rows"]
    later = []
    names = list(library)
    for a, b in product(names, repeat=2):
        later.append(((a, b), compose(library[a], library[b])))
    # task: bearing to node 5. acquired then in should do it.
    hits = [seq for seq, rows in later if 5 in bits(rows[0])]
    checks = {
        "qualified": qualified and chosen[0] == ("in", "in"),
        "stored": loaded.get("seq") == ["in", "in"],
        "later_uses_it": ("acquired", "in") in hits,
        "not_told": "acquired" in names and "in-in" not in names,
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "hits": [list(h) for h in hits],
        "failed": failed,
        "claim": "later search used the stored program; it was not named in-in"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/geom_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
