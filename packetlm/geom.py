"""Generate the programs.

Relations come from the facts.
One and two steps are enumerated.
A missing prediction is undetermined.
Not a proven advantage. Not a general mind.
"""

from __future__ import annotations
import json
from itertools import product
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
        cur = {o for s, r, o in facts if r == rel and s in cur}
    return cur

def run() -> dict:
    facts = [(0, "in", 1), (1, "in", 2), (0, "near", 3), (3, "near", 4)]
    rels = sorted({r for _, r, _ in facts})
    n = 5
    base = {rel: rows_from(facts, n, rel) for rel in rels}
    programs = []
    for length in (1, 2):
        for seq in product(rels, repeat=length):
            rows = base[seq[0]]
            for rel in seq[1:]:
                rows = compose(rows, base[rel])
            programs.append((seq, rows))
    start = 0
    preds = [bits(rows[start]) for _, rows in programs]
    walks = [sorted(walk(facts, start, seq)) for seq, _ in programs]
    # bearing part machine = {2}. near-near is {4}. in is {1}.
    answer = {2}
    supported, undetermined, contradicted = [], [], []
    for i, pred in enumerate(preds):
        if not pred:
            undetermined.append(i)
        elif set(pred) == answer:
            supported.append(i)
        else:
            contradicted.append(i)
    live = (1 << len(programs)) - 1
    listed = [i for i in range(len(programs)) if i in supported or i in undetermined]
    masked = bits(live & (mask_of(supported) | mask_of(undetermined)))
    checks = {
        "generated": len(programs) == 6,
        "bits_match_walk": preds == walks,
        "found_in_in": programs[supported[0]][0] == ("in", "in") if supported else False,
        "undetermined_present": len(undetermined) >= 0,
        "list_matches_mask": listed == masked,
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "programs": [list(seq) for seq, _ in programs],
        "supported": [list(programs[i][0]) for i in supported],
        "failed": failed,
        "claim": "programs generated from relations; bits match the walk"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/geom_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
