"""Gate.

Unique and fully judged, or withhold.
The gate does not name the target sequence.
Transfer stays.
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

def compile_seq(base, seq):
    rows = base[seq[0]]
    for rel in seq[1:]:
        rows = compose(rows, base[rel])
    return rows

def walk(facts, start, seq):
    cur = {start}
    for rel in seq:
        cur = {o for s, r, o in facts if r == rel and s in cur}
    return cur

def classify(facts, n, answer):
    rels = sorted({r for _, r, _ in facts})
    base = {rel: rows_from(facts, n, rel) for rel in rels}
    supported, undetermined = [], []
    for length in (1, 2):
        for seq in product(rels, repeat=length):
            pred = bits(compile_seq(base, seq)[0])
            if not pred:
                undetermined.append(seq)
            elif set(pred) == answer:
                supported.append(seq)
    return supported, undetermined

def run() -> dict:
    incomplete = [
        (0, "in", 1), (1, "in", 2),
        (0, "near", 3),
    ]
    inc_sup, inc_und = classify(incomplete, 4, {2})
    withheld = not (len(inc_sup) == 1 and not inc_und)
    complete = [
        (0, "in", 1), (1, "in", 2),
        (0, "near", 3), (3, "near", 6),
        (1, "near", 3), (3, "in", 4),
    ]
    supported, undetermined = classify(complete, 7, {2})
    qualified = len(supported) == 1 and not undetermined
    save(STATE, {"seq": list(supported[0])} if qualified else {})
    loaded = load(STATE)
    new_facts = [(10, "in", 11), (11, "in", 12)]
    seq = tuple(loaded.get("seq", []))
    new_base = {"in": rows_from(new_facts, 13, "in"), "near": rows_from(new_facts, 13, "near")}
    compiled = compile_seq(new_base, seq) if len(seq) == 2 else None
    checks = {
        "incomplete_withheld": withheld,
        "qualified": qualified,
        "gate_unnamed": qualified and len(supported) == 1,
        "transferred": compiled is not None and bits(compiled[10]) == sorted(walk(new_facts, 10, seq)),
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "seq": loaded.get("seq"),
        "failed": failed,
        "claim": "incomplete withholds; complete qualifies; sequence transfers"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/geom_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
