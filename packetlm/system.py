"""Propagation with a negative.

Dax tails go green. Mira and Orion inherit.
Sam is not a dax. Sam must not inherit green.
Ancestor still walks to cy.
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

def member_tail(field, name, objects):
    kind = ask(field, name, "isa", objects)
    if not kind:
        return None
    return ask(field, kind, "tail", objects)

def run() -> dict:
    objects = ["bea", "cy", "dax", "blue", "green", "needle", "cat"]
    field = []
    for s, r, o in [
        ("ann", "ancestor", "bea"),
        ("bea", "ancestor", "cy"),
        ("dax", "tail", "blue"),
        ("mira", "isa", "dax"),
        ("orion", "isa", "dax"),
        ("sam", "isa", "cat"),
        ("lily", "found", "needle"),
    ]:
        add(field, s, r, o)
    field = [f for f in field if not (f["s"] == "dax" and f["r"] == "tail")]
    add(field, "dax", "tail", "green")
    save(FIELD, field)
    loaded = load(FIELD)
    ancestor = walk(loaded, "ann", "ancestor", objects)
    checks = {
        "mira_green": member_tail(loaded, "mira", objects) == "green",
        "orion_green": member_tail(loaded, "orion", objects) == "green",
        "sam_not_green": member_tail(loaded, "sam", objects) != "green",
        "derived_cy": ancestor == ["bea", "cy"],
        "retained": ask(loaded, "lily", "found", objects) == "needle",
        "reloaded": len(loaded) == len(field),
        "tight_won": Router(
            [hash_to_bits("lily needle"), hash_to_bits("lily needle river stones dusk")]
        ).select(hash_to_bits("lily needle"), 1)[0][0].bits == hash_to_bits("lily needle").bits,
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "ancestor_walk": ancestor,
        "sam_tail": member_tail(loaded, "sam", objects),
        "failed": failed,
        "claim": "members inherit; non-members do not; not a mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/system_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
