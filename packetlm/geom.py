"""Speak what transferred.

Incomplete still withholds.
The sequence still compiles on a new graph.
The conclusion is spoken through an acquired construction.
Not a general mind.
"""

from __future__ import annotations
import json
from itertools import product
from pathlib import Path
from .field import save, load
from .roles import induce, select

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

def express(construction, fact):
    s, r, o = fact
    if not construction or r != construction["meaning"]:
        return None
    roles = {"s": s, "r": construction["word"], "o": o}
    return " ".join(roles[role] for role in construction["order"])

def run() -> dict:
    incomplete = [(0, "in", 1), (1, "in", 2), (0, "near", 3)]
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
    reached = bits(compiled[10]) if compiled else []
    part = induce([("ada part box", ("ada", "part", "box")), ("ned part key", ("ned", "part", "key"))])
    spoken = express(part, ("n10", "part", "n12")) if reached == [12] else None
    back = select([part], spoken) if spoken else None
    checks = {
        "incomplete_withheld": withheld,
        "qualified": qualified,
        "transferred": reached == [12],
        "spoken": spoken == "n10 part n12",
        "roundtrip": back == ("n10", "part", "n12"),
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {**checks, "spoken": spoken, "failed": failed, "claim": "transferred conclusion spoken through an acquired construction"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/geom_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
