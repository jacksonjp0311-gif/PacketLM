"""Range from examples.

Colors seen in examples are allowed.
Long was never a color, so it is rejected.
Operator induction and language feed stay.
Not a general mind.
"""

from __future__ import annotations
import json
from collections import Counter, defaultdict
from pathlib import Path
from .field import add, ask, save, load
from .roles import induce, select

STATE = Path("data/runtime_state.json")

def induce_op(examples):
    keys = Counter(examples)
    if len(keys) != 1:
        return None
    (first, second, out), n = next(iter(keys.items()))
    return (first, second, out) if n >= 2 else None

def induce_range(examples):
    """examples: (relation, value)."""
    out = defaultdict(set)
    for rel, val in examples:
        out[rel].add(val)
    return {k: v for k, v in out.items() if len(v) >= 1}

def answer(field, subject, want, objects, ranges):
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
        allowed = ranges.get(want)
        if allowed is not None and val not in allowed:
            return {"rel": want, "value": val, "valid": False}
        return {"rel": want, "value": val, "via": first, "valid": True}
    return None

def run() -> dict:
    op = induce_op([("isa", "tail", "hastail"), ("isa", "tail", "hastail")])
    ranges = induce_range([("color", "green"), ("color", "blue"), ("hastail", "green")])
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
    good = answer(field, "orion", "hastail", objects, ranges)
    field = [f for f in field if not (f["s"] == "dax" and f["r"] == "tail")]
    add(field, "dax", "tail", "long")
    field = [f for f in field if not (f["s"] == "isa" and f["r"] == "compose")]
    add(field, "isa", "compose", "color")
    invalid = answer(field, "orion", "color", objects, ranges)
    save(STATE, field)
    checks = {
        "op_induced": op == ("isa", "tail", "hastail"),
        "range_from_examples": ranges.get("color") == {"green", "blue"},
        "from_language": fact == ("orion", "isa", "dax") and good and good.get("valid"),
        "long_not_a_color": invalid == {"rel": "color", "value": "long", "valid": False},
        "reloaded": len(load(STATE)) == len(field),
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "ranges": {k: sorted(v) for k, v in ranges.items()},
        "failed": failed,
        "claim": "range induced from examples; long is not a color"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/runtime_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
