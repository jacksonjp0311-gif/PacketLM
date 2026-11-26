"""Unified runtime, small.

The operator's stored value is the output relation.
Change it. The answer relation changes.
Not a general mind.
"""

from __future__ import annotations
import json
from pathlib import Path
from .field import add, ask, save, load

STATE = Path("data/runtime_state.json")

def answer(field, subject, want, objects):
    """Pick the operator whose output is want. Apply its chain."""
    for op in [f for f in field if f["r"] == "compose" and f["o"] == want]:
        first = op["s"]
        second = ask(field, first, "chain", objects)
        if not second:
            continue
        mid = ask(field, subject, first, objects)
        if not mid:
            continue
        val = ask(field, mid, second, objects)
        if val:
            return {"rel": want, "value": val, "via": first}
    return None

def run() -> dict:
    objects = ["isa", "tail", "hastail", "color", "green", "dax", "mira"]
    field = []
    add(field, "isa", "chain", "tail")
    add(field, "isa", "compose", "hastail")
    add(field, "mira", "isa", "dax")
    add(field, "dax", "tail", "green")
    got = answer(field, "mira", "hastail", objects)
    # change the operator value
    field = [f for f in field if not (f["s"] == "isa" and f["r"] == "compose")]
    add(field, "isa", "compose", "color")
    changed = answer(field, "mira", "color", objects)
    old = answer(field, "mira", "hastail", objects)
    save(STATE, field)
    loaded = load(STATE)
    checks = {
        "first": got == {"rel": "hastail", "value": "green", "via": "isa"},
        "changed_relation": changed == {"rel": "color", "value": "green", "via": "isa"},
        "old_gone": old is None,
        "reloaded": answer(loaded, "mira", "color", objects) == changed,
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {**checks, "failed": failed, "claim": "operator value is the answer relation; change it and the relation changes"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/runtime_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
