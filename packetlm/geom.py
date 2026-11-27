"""Select, don't hand.

The library has part and owns.
The stored relation picks one.
Two matches abstain.
Not a general mind.
"""

from __future__ import annotations
import json
from itertools import product
from pathlib import Path
from .engine import choose, express
from .field import save, load
from .roles import induce, select

STATE = Path("data/geom_state.json")
NAMES = {10: "alpha", 12: "gamma"}

def bits(m):
    """Set-bit positions, lowest first; visits only set bits (lowest-set-bit isolation)."""
    out = []
    while m:
        low = m & -m
        out.append(low.bit_length() - 1)
        m ^= low
    return out

def rows_from(facts, n, rel):
    rows = [0] * n
    for s, r, o in facts:
        if r == rel:
            rows[s] |= 1 << o
    return rows

def compose(a_rows, b_rows):
    out = []
    for a in a_rows:
        acc, row = 0, a
        while row:  # visit set bits only: OR the rows of the active sources
            low = row & -row
            acc |= b_rows[low.bit_length() - 1]
            row ^= low
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


def run() -> dict:
    complete = [
        (0, "in", 1), (1, "in", 2),
        (0, "near", 3), (3, "near", 6),
        (1, "near", 3), (3, "in", 4),
    ]
    supported, undetermined = classify(complete, 7, {2})
    qualified = len(supported) == 1 and not undetermined
    save(STATE, {"seq": list(supported[0]), "out": "part"} if qualified else {})
    loaded = load(STATE)
    library = [
        induce([("ada part box", ("ada", "part", "box")), ("ned part key", ("ned", "part", "key"))]),
        induce([("ada owns box", ("ada", "owns", "box")), ("ned owns key", ("ned", "owns", "key"))]),
    ]
    seq = tuple(loaded.get("seq", []))
    facts = [(10, "in", 11), (11, "in", 12)]
    base = {"in": rows_from(facts, 13, "in"), "near": rows_from(facts, 13, "near")}
    reached = bits(compile_seq(base, seq)[10]) if len(seq) == 2 else []
    construction = choose(library, loaded.get("out"))
    fact = (NAMES[10], loaded.get("out"), NAMES[reached[0]]) if len(reached) == 1 and construction else None
    spoken = express(construction, fact) if fact else None
    clash = choose(library + [library[0]], "part")
    checks = {
        "qualified": qualified,
        "selected": construction is not None and construction["meaning"] == "part",
        "spoken": spoken == "alpha part gamma",
        "roundtrip": select([construction], spoken) == fact,
        "clash_abstain": clash is None,
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {**checks, "spoken_text": spoken, "failed": failed, "claim": "construction selected from the library; a clash abstains"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/geom_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
