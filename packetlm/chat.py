"""One turn, with correction.

A correction replaces the fact.
The next answer must change.
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
    if len(parts) == 4 and parts[0] == "what" and parts[1] == "does" and parts[3] == "own":
        owned = ask(field, parts[2], "owns", objects)
        return f"{parts[2]} owns {owned}" if owned else "unknown"
    return "unparsed"

def run_lines(lines):
    owns = induce([("ada owns box", ("ada", "owns", "box")), ("ned owns key", ("ned", "owns", "key"))])
    field, objects = [], []
    replies = [turn(field, objects, [owns], line) for line in lines]
    save(STATE, field)
    return replies, field

def run() -> dict:
    script = Path("data/dialogue.txt")
    lines = [ln for ln in script.read_text().splitlines() if ln.strip()] if script.exists() else []
    replies, _ = run_lines(lines)
    loaded = load(STATE)
    checks = {
        "recorded": replies[0] == "recorded rex owns map",
        "before": replies[1] == "rex owns map",
        "corrected": replies[2] == "corrected rex owns key",
        "after": replies[3] == "rex owns key",
        "unknown": replies[4] == "unknown",
        "reloaded": any(f["s"] == "rex" and f["o"] == "key" for f in loaded),
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {"replies": replies, **checks, "failed": failed, "claim": "same turn corrects; the answer changes"}
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
