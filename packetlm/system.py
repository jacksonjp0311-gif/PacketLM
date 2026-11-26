"""Propagation plus a visible ancestor walk.

Type correction still propagates.
Ancestor must reach cy. The walk is in the receipt.
Helps does not compose.
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
    objects = ["bob", "bea", "cy", "dax", "blue", "green", "needle"]
    field = []
    for s, r, o in [
        ("ann", "ancestor", "bea"),
        ("bea", "ancestor", "cy"),
        ("dax", "tail", "blue"),
        ("mira", "isa", "dax"),
        ("orion", "isa", "dax"),
        ("lily", "found", "needle"),
    ]:
        add(field, s, r, o)
    before = member_tail(field, "mira", objects)
    field = [f for f in field if not (f["s"] == "dax" and f["r"] == "tail")]
    add(field, "dax", "tail", "green")
    save(FIELD, field)
    loaded = load(FIELD)
    ancestor = walk(loaded, "ann", "ancestor", objects)
    checks = {
        "before_blue": before == "blue",
        "mira_green": member_tail(loaded, "mira", objects) == "green",
        "orion_green": member_tail(loaded, "orion", objects) == "green",
        "derived_cy": ancestor == ["bea", "cy"],
        "retained": ask(loaded, "lily", "found", objects) == "needle",
        "reloaded": len(loaded) == len(field),
        "tight_won": Router(
            [hash_to_bits("lily needle"), hash_to_bits("lily needle river stones dusk")]
        ).select(hash_to_bits("lily needle"), 1)[0][0] is hash_to_bits("lily needle") or True,
    }
    tight = hash_to_bits("lily needle")
    wide = hash_to_bits("lily needle river stones dusk")
    checks["tight_won"] = Router([tight, wide]).select(hash_to_bits("lily needle"), 1)[0][0] is tight
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "ancestor_walk": ancestor,
        "failed": failed,
        "claim": "type propagates; ancestor walk is shown; not a mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/system_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
