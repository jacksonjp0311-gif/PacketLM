"""The relation comes from the store.

A missing name abstains.
Not a general mind.
"""

from __future__ import annotations
import json
from itertools import product
from pathlib import Path
from .field import save, load
from .roles import induce, select

STATE = Path("data/geom_state.json")
NAMES = {10: "alpha", 12: "gamma", 20: "delta", 22: "omega"}

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

def speak(construction, start, reached, out_rel):
    if len(reached) != 1 or start not in NAMES or reached[0] not in NAMES:
        return None, None
    fact = (NAMES[start], out_rel, NAMES[reached[0]])
    return express(construction, fact), fact

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
    save(STATE, {"seq": list(supported[0]), "out": "part"} if qualified else {})
    loaded = load(STATE)
    part = induce([("ada part box", ("ada", "part", "box")), ("ned part key", ("ned", "part", "key"))])
    seq = tuple(loaded.get("seq", []))
    out_rel = loaded.get("out")
    graphs = {10: [(10, "in", 11), (11, "in", 12)], 20: [(20, "in", 21), (21, "in", 22)]}
    spoken = {}
    for start, facts in graphs.items():
        base = {"in": rows_from(facts, 23, "in"), "near": rows_from(facts, 23, "near")}
        reached = bits(compile_seq(base, seq)[start]) if len(seq) == 2 else []
        said, fact = speak(part, start, reached, out_rel)
        spoken[start] = {"said": said, "fact": fact}
    checks = {
        "incomplete_withheld": withheld,
        "from_store": out_rel == "part" and spoken[10]["said"] == "alpha part gamma",
        "changes": spoken[20]["said"] == "delta part omega",
        "unknown_name": speak(part, 99, [12], out_rel) == (None, None),
        "roundtrip": select([part], spoken[10]["said"]) == spoken[10]["fact"],
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {**checks, "failed": failed, "claim": "relation comes from the store; a missing name abstains"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/geom_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
