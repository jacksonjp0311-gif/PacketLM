"""A stored operator.

Examples: parent of parent is grandparent.
The operator is a fact in the field, not a Python branch.
Apply it to a pair that was not in the examples.
Propagation checks stay.
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
    """If a mid_rel b and b mid_rel c, and op says mid_rel+mid_rel = out_rel, return c."""
    out_rel = ask(field, mid_rel, "compose", objects)
    if not out_rel:
        return None
    b = ask(field, a, mid_rel, objects)
    if not b:
        return None
    return ask(field, b, mid_rel, objects)

def run() -> dict:
    objects = ["bea", "cy", "dax", "cat", "blue", "green", "long", "needle", "parent", "grand", "jo", "kim", "lee"]
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
        ("ned", "parent", "lee"),
    ]:
        add(field, s, r, o)
    before = prop(field, "mira", "tail", objects)
    field = [f for f in field if not (f["s"] == "dax" and f["r"] == "tail")]
    add(field, "dax", "tail", "green")
    save(FIELD, field)
    loaded = load(FIELD)
    after = prop(loaded, "mira", "tail", objects)
    # apply stored operator to a pair: ada parent jo parent kim => kim
    derived = apply_op(loaded, "ada", "parent", objects)
    # ned parent lee has no further parent; operator should not invent one
    ned = apply_op(loaded, "ned", "parent", objects)
    checks = {
        "before_blue": before == "blue",
        "after_green": after == "green",
        "sam_stayed_long": prop(loaded, "sam", "whiskers", objects) == "long",
        "op_applied": derived == "kim",
        "op_no_invent": ned is None,
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
        "derived_grand": derived,
        "rule": "operator stored as parent compose grand; application is still our code",
        "failed": failed,
        "claim": "operator lives in the field; applied to a new pair; not learned; not a mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/system_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
