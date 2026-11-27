"""Transfer, after the empty path is resolved.

near then near now predicts a wrong node.
The sequence is stored and compiled on a new graph.
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

def run() -> dict:
    facts = [
        (0, "in", 1), (1, "in", 2),
        (0, "near", 3), (3, "near", 6),
        (1, "near", 3), (3, "in", 4),
    ]
    rels = sorted({r for _, r, _ in facts})
    base = {rel: rows_from(facts, 7, rel) for rel in rels}
    programs = []
    for length in (1, 2):
        for seq in product(rels, repeat=length):
            programs.append((seq, compile_seq(base, seq)))
    supported = [seq for seq, rows in programs if set(bits(rows[0])) == {2}]
    undetermined = [seq for seq, rows in programs if not bits(rows[0])]
    qualified = supported == [("in", "in")] and not undetermined
    save(STATE, {"seq": list(supported[0])} if qualified else {})
    loaded = load(STATE)
    new_facts = [(10, "in", 11), (11, "in", 12), (10, "near", 13)]
    new_base = {rel: rows_from(new_facts, 14, rel) for rel in ("in", "near")}
    seq = tuple(loaded.get("seq", []))
    compiled = compile_seq(new_base, seq) if len(seq) == 2 else None
    checks = {
        "qualified": qualified,
        "stored_seq": loaded.get("seq") == ["in", "in"],
        "no_rows_stored": "rows" not in (loaded or {}),
        "transferred": compiled is not None and bits(compiled[10]) == sorted(walk(new_facts, 10, seq)) == [12],
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "undetermined": [list(s) for s in undetermined],
        "supported": [list(s) for s in supported],
        "failed": failed,
        "claim": "empty path resolved; sequence compiled on a new graph"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/geom_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
