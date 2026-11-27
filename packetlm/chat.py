"""One turn.

A script and a terminal call the same function.
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
    parts = line.lower().strip().rstrip("?").rstrip(".").split()
    fact = select(library, line.lower().strip().rstrip("."))
    if fact:
        add(field, *fact)
        for t in fact:
            if t not in objects:
                objects.append(t)
        return f"recorded {fact[0]} {fact[1]} {fact[2]}"
    if len(parts) == 4 and parts[0] == "what" and parts[1] == "does" and parts[3] == "own":
        owned = ask(field, parts[2], "owns", objects)
        return f"{parts[2]} owns {owned}" if owned else "unknown"
    return "unparsed"

def run_lines(lines):
    owns = induce([("ada owns box", ("ada", "owns", "box")), ("ned owns key", ("ned", "owns", "key"))])
    library = [owns]
    field, objects = [], []
    replies = [turn(field, objects, library, line) for line in lines]
    save(STATE, field)
    return replies, field

def run() -> dict:
    script = Path("data/dialogue.txt")
    lines = script.read_text().splitlines() if script.exists() else ["rex owns map", "what does rex own"]
    replies, field = run_lines(lines)
    loaded = load(STATE)
    checks = {
        "recorded": replies[0] == "recorded rex owns map",
        "answered": replies[1] == "rex owns map",
        "unknown": replies[2] == "unknown",
        "reloaded": any(f["s"] == "rex" and f["o"] == "map" for f in loaded),
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {"replies": replies, **checks, "failed": failed, "claim": "script and terminal share turn"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/chat_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    if "--script" in sys.argv:
        path = sys.argv[sys.argv.index("--script") + 1]
        replies, _ = run_lines(Path(path).read_text().splitlines())
        for line in replies:
            print(line)
    elif "--interactive" in sys.argv:
        owns = induce([("ada owns box", ("ada", "owns", "box")), ("ned owns key", ("ned", "owns", "key"))])
        field, objects = [], []
        while True:
            try:
                line = input("> ")
            except EOFError:
                break
            if line.strip() in {"quit", "exit"}:
                break
            print(turn(field, objects, [owns], line))
    else:
        run()
