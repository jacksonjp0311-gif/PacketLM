"""Operator from examples. Range checked.

Two examples of isa then tail writing hastail induce the operator.
A color whose value is not in the color range is rejected.
Language still feeds the field.
Not a general mind.
"""

from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
from .field import add, ask, save, load
from .roles import induce, select

STATE = Path("data/runtime_state.json")
RANGE = {"color": {"green", "blue", "red"}, "hastail": {"green", "blue"}}

def induce_op(examples):
    """examples: (first, second, out). Two agreeing triples store the operator."""
    keys = Counter(examples)
    if len(keys) != 1:
        return None
    (first, second, out), n = next(iter(keys.items()))
    if n < 2:
        return None
    return first, second, out

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
        if not val:
            continue
        allowed = RANGE.get(want)
        if allowed is not None and val not in allowed:
            return {"rel": want, "value": val, "valid": False}
        return {"rel": want, "value": val, "via": first, "hop": second, "valid": True}
    return None

def run() -> dict:
    op = induce_op([("isa", "tail", "hastail"), ("isa", "tail", "hastail")])
    bad_op = induce_op([("isa", "tail", "hastail"), ("isa", "tail", "color")])
    isa = induce([("mira isa dax", ("mira", "isa", "dax")), ("sam isa cat", ("sam", "isa", "cat"))])
    fact = select([isa], "orion isa dax") if isa else None
    objects = ["isa", "tail", "hastail", "color", "green", "long", "dax"]
    field = []
    if fact:
        add(field, *fact)
    if op:
        add(field, op[0], "chain", op[1])
        add(field, op[0], "compose", op[2])
    add(field, "dax", "tail", "green")
    good = answer(field, "orion", "hastail", objects)
    field = [f for f in field if not (f["s"] == "dax" and f["r"] == "tail")]
    add(field, "dax", "tail", "long")
    field = [f for f in field if not (f["s"] == "isa" and f["r"] == "compose")]
    add(field, "isa", "compose", "color")
    invalid = answer(field, "orion", "color", objects)
    save(STATE, field)
    checks = {
        "op_induced": op == ("isa", "tail", "hastail"),
        "disagreement_rejected": bad_op is None,
        "from_language": fact == ("orion", "isa", "dax") and good == {"rel": "hastail", "value": "green", "via": "isa", "hop": "tail", "valid": True},
        "range_rejected": invalid == {"rel": "color", "value": "long", "valid": False},
        "reloaded": len(load(STATE)) == len(field),
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {**checks, "failed": failed, "claim": "operator induced; a color that is not a color is rejected"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/runtime_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
