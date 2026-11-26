"""Chat through acquired language.

Statements are selected, not parsed by hand.
A fact is spoken by reversing the construction.
Not a general mind.
"""

from __future__ import annotations
import json
from pathlib import Path
from .field import add, ask, save, load
from .roles import induce, select

STATE = Path("data/chat_state.json")

def express(construction, fact):
    if not construction or not fact:
        return None
    s, r, o = fact
    if r != construction["meaning"]:
        return None
    order = construction["order"]
    roles = {"s": s, "r": construction["word"], "o": o}
    return " ".join(roles[role] for role in order)

def run() -> dict:
    isa = induce([("mira isa dax", ("mira", "isa", "dax")), ("sam isa cat", ("sam", "isa", "cat"))])
    owns = induce([("ada owns box", ("ada", "owns", "box")), ("ned owns key", ("ned", "owns", "key"))])
    library = [c for c in (isa, owns) if c]
    objects = ["dax", "green", "red"]
    field = []
    add(field, "dax", "tail", "green")
    membership = select(library, "orion isa dax")
    if membership:
        add(field, *membership)
    kind = ask(field, "orion", "isa", objects)
    color = ask(field, kind, "tail", objects) if kind else None
    spoken = express(owns, ("rex", "owns", "map"))
    roundtrip = select(library, spoken) if spoken else None
    save(STATE, field)
    checks = {
        "selected": membership == ("orion", "isa", "dax"),
        "answered": color == "green",
        "expressed": spoken == "rex owns map",
        "roundtrip": roundtrip == ("rex", "owns", "map"),
        "unknown_verb": select(library, "rex holds map") is None,
        "reloaded": ask(load(STATE), "orion", "isa", objects) == "dax",
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {**checks, "spoken": spoken, "failed": failed, "claim": "construction interprets and expresses; not a live loop"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/chat_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
