"""Mixed-relation operator.

isa chain tail, isa compose hastail.
Mira isa dax, dax tail green => mira hastail green.
The two input relations are different.
Same-relation operators stay.
Not a general mind.
"""

from __future__ import annotations
import json
from pathlib import Path
from .field import add, ask, save, load
from .packets import hash_to_bits
from .router import Router

FIELD = Path("data/system_field.json")

def walk(field, start, relation, objects, steps=3):
    out, cur = [], start
    for _ in range(steps):
        nxt = ask(field, cur, relation, objects)
        if not nxt:
            break
        out.append(nxt)
        cur = nxt
    return out

def apply_same(field, a, mid_rel, objects):
    out_rel = ask(field, mid_rel, "compose", objects)
    if not out_rel:
        return None
    b = ask(field, a, mid_rel, objects)
    if not b:
        return None
    c = ask(field, b, mid_rel, objects)
    if not c:
        return None
    add(field, a, out_rel, c)
    return out_rel, c

def apply_mixed(field, a, first_rel, objects):
    second = ask(field, first_rel, "chain", objects)
    out_rel = ask(field, first_rel, "compose", objects)
    if not second or not out_rel:
        return None
    b = ask(field, a, first_rel, objects)
    if not b:
        return None
    c = ask(field, b, second, objects)
    if not c:
        return None
    add(field, a, out_rel, c)
    return out_rel, c

def run() -> dict:
    objects = [
        "bea", "cy", "dax", "cat", "green", "long", "needle",
        "parent", "grand", "tail", "hastail", "jo", "kim",
    ]
    field = []
    for s, r, o in [
        ("ann", "ancestor", "bea"),
        ("bea", "ancestor", "cy"),
        ("dax", "tail", "green"),
        ("cat", "whiskers", "long"),
        ("mira", "isa", "dax"),
        ("sam", "isa", "cat"),
        ("lily", "found", "needle"),
        ("parent", "compose", "grand"),
        ("isa", "chain", "tail"),
        ("isa", "compose", "hastail"),
        ("ada", "parent", "jo"),
        ("jo", "parent", "kim"),
    ]:
        add(field, s, r, o)
    parent_out = apply_same(field, "ada", "parent", objects)
    mixed = apply_mixed(field, "mira", "isa", objects)
    sam_mixed = apply_mixed(field, "sam", "isa", objects)
    save(FIELD, field)
    loaded = load(FIELD)
    checks = {
        "wrote_grand": parent_out == ("grand", "kim") and ask(loaded, "ada", "grand", objects) == "kim",
        "wrote_hastail": mixed == ("hastail", "green") and ask(loaded, "mira", "hastail", objects) == "green",
        "sam_no_tail": sam_mixed is None,
        "derived_cy": walk(loaded, "ann", "ancestor", objects) == ["bea", "cy"],
        "retained": ask(loaded, "lily", "found", objects) == "needle",
        "reloaded": len(loaded) == len(field),
        "tight_won": Router(
            [hash_to_bits("lily needle"), hash_to_bits("lily needle river stones dusk")]
        ).select(hash_to_bits("lily needle"), 1)[0][0].bits == hash_to_bits("lily needle").bits,
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "mixed": mixed,
        "failed": failed,
        "claim": "mixed operator isa then tail writes hastail; sam has no tail to chain"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/system_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
