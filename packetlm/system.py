"""Correction that propagates.

Daxes have blue tails. Mira is a dax.
Correct the type: daxes have green tails.
Mira's tail is derived, not stored.
Helps still does not compose.
Not a general mind.
"""

from __future__ import annotations
import json
from pathlib import Path
from .field import add, ask, save, load
from .packets import hash_to_bits
from .router import Router

FIELD = Path("data/system_field.json")
TRANSITIVE = {"ancestor"}

def compose(field, start, relation, objects, steps=3):
    if relation not in TRANSITIVE:
        return []
    walked, cur = [], start
    for _ in range(steps):
        nxt = ask(field, cur, relation, objects)
        if not nxt:
            break
        walked.append(nxt)
        cur = nxt
    return walked

def member_tail(field, name, objects) -> str | None:
    kind = ask(field, name, "isa", objects)
    if not kind:
        return None
    return ask(field, kind, "tail", objects)

def run() -> dict:
    objects = ["bob", "cara", "dee", "cy", "dax", "blue", "green", "needle"]
    field = []
    for s, r, o in [
        ("ann", "ancestor", "bea"),
        ("bea", "ancestor", "cy"),
        ("alice", "helps", "bob"),
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
    after_mira = member_tail(loaded, "mira", objects)
    after_orion = member_tail(loaded, "orion", objects)
    checks = {
        "before_blue": before == "blue",
        "mira_green": after_mira == "green",
        "orion_green": after_orion == "green",
        "derived_cy": compose(loaded, "ann", "ancestor", objects)[-1:] == ["cy"],
        "helps_not_composed": compose(loaded, "alice", "helps", objects) == [],
        "retained": ask(loaded, "lily", "found", objects) == "needle",
        "reloaded": len(loaded) == len(field),
        "tight_won": Router([hash_to_bits("lily needle"), hash_to_bits("lily needle river stones")]).select(hash_to_bits("lily needle"), 1)[0][0] is not None,
    }
    # tight check properly
    tight = hash_to_bits("lily needle")
    wide = hash_to_bits("lily needle river stones dusk")
    checks["tight_won"] = Router([tight, wide]).select(hash_to_bits("lily needle"), 1)[0][0] is tight
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "failed": failed,
        "claim": "type correction propagates to members; member tails were not rewritten"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/system_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
