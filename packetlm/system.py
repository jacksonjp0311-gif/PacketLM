"""The operator means something.

parent compose grand is stored.
The returned value grand is the output relation.
We write the derived fact under that relation.
If the operator said something else, the output relation would change.
Sibling has no operator, so it does not run.
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

def run() -> dict:
    objects = [
        "bea", "cy", "dax", "cat", "blue", "green", "long", "needle",
        "parent", "grand", "sibling", "jo", "kim", "lee", "sol", "tan",
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
        ("ada", "sibling", "lee"),
    ]:
        add(field, s, r, o)
    before = prop(field, "mira", "tail", objects)
    field = [f for f in field if not (f["s"] == "dax" and f["r"] == "tail")]
    add(field, "dax", "tail", "green")
    applied = apply_op(field, "ada", "parent", objects)
    sibling = apply_op(field, "ada", "sibling", objects)
    save(FIELD, field)
    loaded = load(FIELD)
    checks = {
        "before_blue": before == "blue",
        "after_green": prop(loaded, "mira", "tail", objects) == "green",
        "sam_stayed_long": prop(loaded, "sam", "whiskers", objects) == "long",
        "op_wrote_grand": applied == ("grand", "kim"),
        "readable_as_grand": ask(loaded, "ada", "grand", objects) == "kim",
        "sibling_blocked": sibling is None,
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
        "applied": applied,
        "failed": failed,
        "claim": "operator value is the output relation; grand is written and readable"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/system_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
