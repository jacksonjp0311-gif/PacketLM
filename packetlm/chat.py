"""Two dependents.

Orion and Mira both follow the dax.
Rex's ownership does not move.
Not a general mind.
"""

from __future__ import annotations
import json
import sys
from pathlib import Path
from .field import add, ask, save, load
from .roles import induce, select

STATE = Path("data/chat_state.json")

def turn(field, objects, library, line):
    raw = line.lower().strip().rstrip("?").rstrip(".")
    parts = raw.split()
    if len(parts) == 4 and parts[0] == "correct":
        field[:] = [f for f in field if not (f["s"] == parts[1] and f["r"] == parts[2])]
        add(field, parts[1], parts[2], parts[3])
        if parts[3] not in objects:
            objects.append(parts[3])
        return f"corrected {parts[1]} {parts[2]} {parts[3]}"
    fact = select(library, raw)
    if fact:
        add(field, *fact)
        for t in fact:
            if t not in objects:
                objects.append(t)
        return f"recorded {fact[0]} {fact[1]} {fact[2]}"
    if len(parts) == 5 and parts[0] == "what" and parts[1] == "color" and parts[-1] == "tail":
        kind = ask(field, parts[3], "isa", objects)
        color = ask(field, kind, "tail", objects) if kind else None
        return f"{parts[3]} has a {color} tail" if color else "unknown"
    if len(parts) == 4 and parts[0] == "what" and parts[1] == "does" and parts[3] == "own":
        owned = ask(field, parts[2], "owns", objects)
        return f"{parts[2]} owns {owned}" if owned else "unknown"
    return "unparsed"

def run_lines(lines):
    isa = induce([("mira isa dax", ("mira", "isa", "dax")), ("sam isa cat", ("sam", "isa", "cat"))])
    owns = induce([("ada owns box", ("ada", "owns", "box")), ("ned owns key", ("ned", "owns", "key"))])
    field, objects = [], ["green", "red"]
    add(field, "dax", "tail", "green")
    replies = [turn(field, objects, [isa, owns], line) for line in lines if line.strip()]
    save(STATE, field)
    return replies

def run() -> dict:
    lines = [ln for ln in Path("data/dialogue.txt").read_text().splitlines() if ln.strip()]
    replies = run_lines(lines)
    checks = {
        "orion_before": replies[7] == "orion has a green tail",
        "mira_before": replies[8] == "mira has a green tail",
        "premise": replies[9] == "corrected dax tail red",
        "orion_after": replies[10] == "orion has a red tail",
        "mira_after": replies[11] == "mira has a red tail",
        "unrelated": replies[12] == "rex owns key",
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {"replies": replies, **checks, "failed": failed, "claim": "two dependents move; unrelated fact stays"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/chat_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    if "--interactive" in sys.argv:
        isa = induce([("mira isa dax", ("mira", "isa", "dax")), ("sam isa cat", ("sam", "isa", "cat"))])
        owns = induce([("ada owns box", ("ada", "owns", "box")), ("ned owns key", ("ned", "owns", "key"))])
        field, objects = [], []
        while True:
            try:
                line = input("> ")
            except EOFError:
                break
            if line.strip() in {"quit", "exit"}:
                break
            print(turn(field, objects, [isa, owns], line))
    else:
        run()
