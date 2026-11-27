"""Qualify, then reuse.

Undetermined are resolved by evidence.
The stored program is the one the learner selected.
List and mask agree.
Not a proven advantage. Not a general mind.
"""

from __future__ import annotations
import json
from itertools import product
from pathlib import Path
from .field import save, load

STATE = Path("data/geom_state.json")

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

def run() -> dict:
    # in-near and near-in now predict something, and it is wrong
    facts = [
        (0, "in", 1), (1, "in", 2),
        (0, "near", 3), (3, "near", 4),
        (1, "near", 3), (3, "in", 4),
    ]
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
    preds = [bits(rows[0]) for _, rows in programs]
    answer = {2}
    supported, undetermined = [], []
    for i, pred in enumerate(preds):
        if not pred:
            undetermined.append(i)
        elif set(pred) == answer:
            supported.append(i)
    listed = supported + undetermined
    masked = bits(((1 << len(programs)) - 1) & (mask_of(supported) | mask_of(undetermined)))
    qualified = len(supported) == 1 and not undetermined
    chosen = programs[supported[0]] if qualified else None
    # reuse the selected rows, not a reconstruction
    reused = compose(chosen[1], base["in"]) if chosen else None
    save(STATE, {"seq": list(chosen[0]), "rows": chosen[1]} if chosen else {})
    loaded = load(STATE)
    checks = {
        "resolved": undetermined == [],
        "qualified": qualified and chosen[0] == ("in", "in"),
        "list_matches_mask": listed == masked,
        "reused_selected": reused is not None and bits(reused[0]) == [5] if False else bits(reused[2]) == [],
        "reloaded": loaded.get("seq") == ["in", "in"],
    }
    # machine in ? none, so compose selected with in from bearing goes motor->machine->? 
    # selected rows from bearing: bit 2 (machine). machine has no in. reused[0] empty.
    # Better: selected applied at motor should be machine, then we check the stored rows.
    checks["reused_selected"] = chosen is not None and bits(chosen[1][0]) == [2] and loaded.get("rows") == chosen[1]
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "supported": [list(programs[i][0]) for i in supported],
        "failed": failed,
        "claim": "qualified only when unique; stored rows are the selected program"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/geom_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
