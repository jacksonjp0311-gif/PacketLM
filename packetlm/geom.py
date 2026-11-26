"""Survivors named. Reuse.

Supported is not unique while undetermined remain.
The acquired in-in is reused as a primitive.
Not a proven advantage. Not a general mind.
"""

from __future__ import annotations
import json
from itertools import product
from pathlib import Path

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
        cur = {o for s, r, o in facts if r == rel and s in cur}
    return cur

def run() -> dict:
    facts = [(0, "in", 1), (1, "in", 2), (0, "near", 3), (3, "near", 4), (2, "in", 5)]
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
    walks = [sorted(walk(facts, 0, seq)) for seq, _ in programs]
    answer = {2}
    supported, undetermined = [], []
    for i, pred in enumerate(preds):
        if not pred:
            undetermined.append(tuple(programs[i][0]))
        elif set(pred) == answer:
            supported.append(tuple(programs[i][0]))
    # reuse: in-in as a primitive, then in
    acquired = base["in"]
    for _ in range(1):
        acquired = compose(acquired, base["in"])
    reused = compose(acquired, base["in"])
    reused_walk = sorted(walk(facts, 0, ["in", "in", "in"]))
    checks = {
        "bits_match_walk": preds == walks,
        "supported_exact": supported == [("in", "in")],
        "undetermined_exact": set(undetermined) == {("in", "near"), ("near", "in")},
        "not_unique": len(supported) + len(undetermined) > 1,
        "reused": bits(reused[0]) == reused_walk == [5],
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "supported": [list(s) for s in supported],
        "undetermined": [list(s) for s in undetermined],
        "failed": failed,
        "claim": "survivors named; acquired program reused; not unique while undetermined remain"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/geom_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
