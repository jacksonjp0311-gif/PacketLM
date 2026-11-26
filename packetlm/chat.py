"""Speak what was derived.

A path is discovered. Orion's tail is derived.
The conclusion is spoken by reversing a construction.
Not a general mind.
"""

from __future__ import annotations
import json
from pathlib import Path
from .field import add, ask, save, load
from .roles import induce, select
from .runtime import discover, apply_path

STATE = Path("data/chat_state.json")

def express(construction, fact):
    if not construction or not fact:
        return None
    s, r, o = fact
    if r != construction["meaning"]:
        return None
    roles = {"s": s, "r": construction["word"], "o": o}
    return " ".join(roles[role] for role in construction["order"])

def run() -> dict:
    isa = induce([("mira isa dax", ("mira", "isa", "dax")), ("sam isa cat", ("sam", "isa", "cat"))])
    hastail = induce([("mira hastail green", ("mira", "hastail", "green")), ("sam hastail blue", ("sam", "hastail", "blue"))])
    objects = ["dax", "cat", "green", "blue", "mira", "sam", "orion"]
    field = []
    for s, r, o in [("mira", "isa", "dax"), ("dax", "tail", "green"), ("sam", "isa", "cat"), ("cat", "tail", "blue"), ("orion", "isa", "dax")]:
        add(field, s, r, o)
    path = discover(field, [("mira", "hastail", "green"), ("sam", "hastail", "blue")], objects)
    derived = apply_path(field, path, "orion", objects)
    fact = ("orion", "hastail", derived) if derived else None
    spoken = express(hastail, fact)
    back = select([hastail], spoken) if spoken else None
    save(STATE, field)
    checks = {
        "path": path == ("isa", "tail", "hastail"),
        "derived": derived == "green",
        "spoken": spoken == "orion hastail green",
        "roundtrip": back == fact,
        "reloaded": ask(load(STATE), "orion", "isa", objects) == "dax",
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {**checks, "spoken": spoken, "failed": failed, "claim": "derived conclusion spoken through an acquired construction"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/chat_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
