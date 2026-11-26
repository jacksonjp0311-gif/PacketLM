"""Language into the operator.

A selected sentence writes the membership.
The operator reads it.
Change the chain. The hop changes.
Change the output. The relation changes.
Not a general mind.
"""

from __future__ import annotations
import json
from pathlib import Path
from .field import add, ask, save, load
from .roles import induce, select

STATE = Path("data/runtime_state.json")

def answer(field, subject, want, objects):
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
            return {"rel": want, "value": val, "via": first, "hop": second}
    return None

def run() -> dict:
    isa = induce([
        ("mira isa dax", ("mira", "isa", "dax")),
        ("sam isa cat", ("sam", "isa", "cat")),
    ])
    fact = select([isa], "orion isa dax") if isa else None
    objects = ["isa", "tail", "whiskers", "hastail", "color", "green", "long", "dax"]
    field = []
    if fact:
        add(field, *fact)
        for t in fact:
            if t not in objects:
                objects.append(t)
    add(field, "isa", "chain", "tail")
    add(field, "isa", "compose", "hastail")
    add(field, "dax", "tail", "green")
    add(field, "dax", "whiskers", "long")
    first = answer(field, "orion", "hastail", objects)
    field = [f for f in field if not (f["s"] == "isa" and f["r"] == "chain")]
    add(field, "isa", "chain", "whiskers")
    hopped = answer(field, "orion", "hastail", objects)
    field = [f for f in field if not (f["s"] == "isa" and f["r"] == "compose")]
    add(field, "isa", "compose", "color")
    renamed = answer(field, "orion", "color", objects)
    save(STATE, field)
    loaded = load(STATE)
    checks = {
        "from_language": fact == ("orion", "isa", "dax") and first == {"rel": "hastail", "value": "green", "via": "isa", "hop": "tail"},
        "hop_changed": hopped == {"rel": "hastail", "value": "long", "via": "isa", "hop": "whiskers"},
        "relation_changed": renamed == {"rel": "color", "value": "long", "via": "isa", "hop": "whiskers"},
        "reloaded": answer(loaded, "orion", "color", objects) == renamed,
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {**checks, "failed": failed, "claim": "language fact feeds the operator; chain and output both change the result"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/runtime_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
