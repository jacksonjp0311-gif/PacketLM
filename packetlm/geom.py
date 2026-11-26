"""Programs execute.

Predictions come from composition, not an array.
A walk is the reference.
List and mask must agree.
Not a proven advantage. Not a general mind.
"""

from __future__ import annotations
import json
from pathlib import Path

def mask_of(ids):
    m = 0
    for i in ids:
        m |= 1 << i
    return m

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

def walk(facts, start, rels):
    cur = {start}
    for rel in rels:
        nxt = set()
        for s, r, o in facts:
            if r == rel and s in cur:
                nxt.add(o)
        cur = nxt
    return cur

def predict(rows, start):
    return bits(rows[start])

def run() -> dict:
    # 0 bearing, 1 motor, 2 machine, 3 bench
    facts = [(0, "in", 1), (1, "in", 2), (0, "near", 3)]
    inn = rows_from(facts, 4, "in")
    near = rows_from(facts, 4, "near")
    programs = {
        "in": inn,
        "in_in": compose(inn, inn),
        "near": near,
    }
    # expected from independent walk
    walks = {
        "in": walk(facts, 0, ["in"]),
        "in_in": walk(facts, 0, ["in", "in"]),
        "near": walk(facts, 0, ["near"]),
    }
    preds = {name: predict(rows, 0) for name, rows in programs.items()}
    # evidence: bearing part machine. which program predicts {2}?
    answer = {2}
    supported = [i for i, name in enumerate(programs) if set(preds[name]) == answer]
    undetermined = []
    live = (1 << len(programs)) - 1
    listed = [i for i in range(len(programs)) if i in supported or i in undetermined]
    masked = bits(live & (mask_of(supported) | mask_of(undetermined)))
    checks = {
        "bits_match_walk": all(set(preds[k]) == walks[k] for k in programs),
        "found": supported == [1],
        "list_matches_mask": listed == masked,
        "one_hop_kept": preds["in"] == [1],
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "preds": preds,
        "walks": {k: sorted(v) for k, v in walks.items()},
        "failed": failed,
        "claim": "programs executed; bits match the walk; list matches the mask"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/geom_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
