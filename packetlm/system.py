"""Two types.

Dax tails go green. Cat whiskers go long.
Mira inherits green, not long.
Sam inherits long, not green.
Ancestor still reaches cy.
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

def run() -> dict:
    objects = ["bea", "cy", "dax", "cat", "green", "long", "needle"]
    field = []
    for s, r, o in [
        ("ann", "ancestor", "bea"),
        ("bea", "ancestor", "cy"),
        ("dax", "tail", "green"),
        ("cat", "whiskers", "long"),
        ("mira", "isa", "dax"),
        ("sam", "isa", "cat"),
        ("lily", "found", "needle"),
    ]:
        add(field, s, r, o)
    save(FIELD, field)
    loaded = load(FIELD)
    ancestor = walk(loaded, "ann", "ancestor", objects)
    checks = {
        "mira_tail": prop(loaded, "mira", "tail", objects) == "green",
        "mira_not_whiskers": prop(loaded, "mira", "whiskers", objects) != "long",
        "sam_whiskers": prop(loaded, "sam", "whiskers", objects) == "long",
        "sam_not_tail": prop(loaded, "sam", "tail", objects) != "green",
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
        "failed": failed,
        "claim": "two types; each member inherits only its own; not a mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/system_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
