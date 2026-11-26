"""A small chat.

Statements write the field.
Questions read it.
A correction revises it.
The reply is the conclusion, not a script.
Not a general mind.
"""

from __future__ import annotations
import json
from pathlib import Path
from .field import add, ask, save, load

STATE = Path("data/chat_state.json")

def turn(field, objects, line):
    parts = line.lower().strip().rstrip("?").rstrip(".").split()
    if len(parts) == 4 and parts[1] == "is" and parts[2] == "a":
        add(field, parts[0], "isa", parts[3])
        for t in (parts[0], parts[3]):
            if t not in objects:
                objects.append(t)
        return f"{parts[0]} is a {parts[3]}"
    if len(parts) == 4 and parts[0] == "correct":
        field[:] = [f for f in field if not (f["s"] == parts[1] and f["r"] == parts[2])]
        add(field, parts[1], parts[2], parts[3])
        if parts[3] not in objects:
            objects.append(parts[3])
        return f"{parts[1]} {parts[2]} is {parts[3]}"
    if len(parts) == 5 and parts[0] == "what" and parts[1] == "color" and parts[-1] == "tail":
        name = parts[3]
        kind = ask(field, name, "isa", objects)
        if not kind:
            return "unknown"
        color = ask(field, kind, "tail", objects)
        if not color:
            return "unknown"
        return f"{name} has a {color} tail"
    return "unparsed"

def run() -> dict:
    objects = ["dax", "green", "red"]
    field = []
    add(field, "dax", "tail", "green")
    lines = [
        "orion is a dax",
        "what color is orion tail?",
        "correct dax tail red",
        "what color is orion tail?",
        "can orion fly?",
    ]
    replies = [turn(field, objects, line) for line in lines]
    save(STATE, field)
    loaded = load(STATE)
    checks = {
        "recorded": replies[0] == "orion is a dax",
        "before": replies[1] == "orion has a green tail",
        "corrected": replies[2] == "dax tail is red",
        "after": replies[3] == "orion has a red tail",
        "unparsed": replies[4] == "unparsed",
        "reloaded": ask(loaded, "orion", "isa", objects) == "dax",
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {"replies": replies, **checks, "failed": failed, "claim": "scripted chat; replies come from the field"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/chat_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
