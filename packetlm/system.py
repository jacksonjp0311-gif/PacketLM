"""One operator, two pairs.

parent compose grand is stored once.
Ada -> Jo -> Kim and Rex -> Sol -> Tan both use it.
A dead end still invents nothing.
Propagation stays.
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

def prop(field, name, relation, objects):
    kind = ask(field, name, "isa", objects)
    if not kind:
        return None
    return ask(field, kind, relation, objects)

def apply_op(field, a, mid_rel, objects):
    if not ask(field, mid_rel, "compose", objects):
        return None
    b = ask(field, a, mid_rel, objects)
    if not b:
        return None
    return ask(field, b, mid_rel, objects)

def run() -> dict:
    objects = [
        "bea", "cy", "dax", "cat", "blue", "green", "long", "needle",
        "parent", "grand", "jo", "kim", "lee", "sol", "tan",
    ]
    field = []
    for s, r, o in [
        ("ann", "ancestor", "bea"),
        ("bea", "ancestor", "cy"),
        ("dax", "tail", "blue"),
        ("cat", "whiskers", "long"),
        ("mira", "isa", "dax"),
        ("sam", "isa", "cat"),
        ("lily", "found", "needle"),
        ("parent", "compose", "grand"),
        ("ada", "parent", "jo"),
        ("jo", "parent", "kim"),
        ("rex", "parent", "sol"),
        ("sol", "parent", "tan"),
        ("ned", "parent", "lee"),
    ]:
        add(field, s, r, o)
    before = prop(field, "mira", "tail", objects)
    field = [f for f in field if not (f["s"] == "dax" and f["r"] == "tail")]
    add(field, "dax", "tail", "green")
    save(FIELD, field)
    loaded = load(FIELD)
    checks = {
        "before_blue": before == "blue",
        "after_green": prop(loaded, "mira", "tail", objects) == "green",
        "sam_stayed_long": prop(loaded, "sam", "whiskers", objects) == "long",
        "op_kim": apply_op(loaded, "ada", "parent", objects) == "kim",
        "op_tan": apply_op(loaded, "rex", "parent", objects) == "tan",
        "op_no_invent": apply_op(loaded, "ned", "parent", objects) is None,
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
        "failed": failed,
        "claim": "one stored operator, two pairs; not learned; not a mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/system_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
