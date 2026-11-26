"""Path discovery.

Facts and expected conclusions are given.
The operator is not.
One path that fits both examples is kept.
Valid, invalid, and unknown are different.
Not a general mind.
"""

from __future__ import annotations
import json
from pathlib import Path
from .field import add, ask, save, load

STATE = Path("data/runtime_state.json")

def discover(field, examples, objects):
    """examples: (subject, out_rel, expected). Search isa-then-property paths."""
    candidates = []
    kinds = {ask(field, s, "isa", objects) for s, _, _ in examples}
    kinds.discard(None)
    props = set()
    for k in kinds:
        for f in field:
            if f["s"] == k:
                props.add(f["r"])
    for prop in props:
        ok = True
        for s, out_rel, expected in examples:
            kind = ask(field, s, "isa", objects)
            val = ask(field, kind, prop, objects) if kind else None
            if val != expected:
                ok = False
                break
        if ok:
            candidates.append(("isa", prop, examples[0][1]))
    return candidates[0] if len(candidates) == 1 else None

def apply_path(field, path, subject, objects):
    if not path:
        return None
    first, second, out = path
    mid = ask(field, subject, first, objects)
    if not mid:
        return None
    return ask(field, mid, second, objects)

def status(value, colors, lengths):
    if value in colors:
        return "valid"
    if value in lengths:
        return "invalid"
    return "unknown"

def run() -> dict:
    objects = ["dax", "cat", "green", "blue", "red", "long", "mira", "sam", "orion"]
    field = []
    for s, r, o in [
        ("mira", "isa", "dax"),
        ("dax", "tail", "green"),
        ("sam", "isa", "cat"),
        ("cat", "tail", "blue"),
        ("orion", "isa", "dax"),
    ]:
        add(field, s, r, o)
    examples = [("mira", "hastail", "green"), ("sam", "hastail", "blue")]
    path = discover(field, examples, objects)
    unseen = apply_path(field, path, "orion", objects)
    colors = {"green", "blue"}
    lengths = {"long"}
    before = status("red", colors, lengths)
    colors.add("red")
    after = status("red", colors, lengths)
    save(STATE, field)
    checks = {
        "discovered": path == ("isa", "tail", "hastail"),
        "unseen": unseen == "green",
        "red_unknown": before == "unknown",
        "red_valid_after": after == "valid",
        "long_invalid": status("long", colors, lengths) == "invalid",
        "reloaded": len(load(STATE)) == len(field),
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {**checks, "path": path, "failed": failed, "claim": "path discovered from conclusions; red starts unknown"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/runtime_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
