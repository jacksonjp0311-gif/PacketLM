"""Propagation, measured.

Before: dax tails are blue. Mira derives blue.
After: dax tails are green. Mira derives green. Blue is gone.
Sam is a cat with long whiskers. That exact property must remain.
The inheritance rule is programmed. It is not learned.
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
    objects = ["bea", "cy", "dax", "cat", "blue", "green", "long", "needle"]
    field = []
    for s, r, o in [
        ("ann", "ancestor", "bea"),
        ("bea", "ancestor", "cy"),
        ("dax", "tail", "blue"),
        ("cat", "whiskers", "long"),
        ("mira", "isa", "dax"),
        ("sam", "isa", "cat"),
        ("lily", "found", "needle"),
    ]:
        add(field, s, r, o)
    before = {
        "mira": prop(field, "mira", "tail", objects),
        "sam": prop(field, "sam", "whiskers", objects),
    }
    field = [f for f in field if not (f["s"] == "dax" and f["r"] == "tail")]
    add(field, "dax", "tail", "green")
    save(FIELD, field)
    loaded = load(FIELD)
    after = {
        "mira": prop(loaded, "mira", "tail", objects),
        "sam": prop(loaded, "sam", "whiskers", objects),
    }
    ancestor = walk(loaded, "ann", "ancestor", objects)
    checks = {
        "before_mira_blue": before["mira"] == "blue",
        "after_mira_green": after["mira"] == "green",
        "blue_gone": after["mira"] != "blue",
        "sam_stayed_long": before["sam"] == "long" and after["sam"] == "long",
        "sam_not_green": prop(loaded, "sam", "tail", objects) != "green",
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
        "before": before,
        "after": after,
        "ancestor_walk": ancestor,
        "rule": "programmed isa then property; not learned",
        "failed": failed,
        "claim": "before and after recorded; negative is the exact other property; not a mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/system_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
