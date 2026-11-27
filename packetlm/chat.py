"""The question does not know the path.

A sequence is found from examples.
The color question applies that sequence.
Not a general mind.
"""

from __future__ import annotations
import json
import sys
from itertools import product
from pathlib import Path
from .field import add, ask, save, load
from .roles import induce, select

STATE = Path("data/chat_state.json")

def discover(field, examples, objects):
    rels = sorted({f["r"] for f in field})
    hits = []
    for seq in product(rels, repeat=2):
        ok = True
        for subject, expected in examples:
            cur = subject
            for rel in seq:
                cur = ask(field, cur, rel, objects)
                if not cur:
                    ok = False
                    break
            if cur != expected:
                ok = False
            if not ok:
                break
        if ok:
            hits.append(seq)
    return hits[0] if len(hits) == 1 else None

def apply_seq(field, seq, subject, objects):
    cur = subject
    for rel in seq or ():
        cur = ask(field, cur, rel, objects)
        if not cur:
            return None
    return cur

def turn(field, objects, library, seq, line):
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
        color = apply_seq(field, seq, parts[3], objects)
        return f"{parts[3]} has a {color} tail" if color else "unknown"
    if len(parts) == 4 and parts[0] == "what" and parts[1] == "does" and parts[3] == "own":
        owned = ask(field, parts[2], "owns", objects)
        return f"{parts[2]} owns {owned}" if owned else "unknown"
    return "unparsed"

def run() -> dict:
    isa = induce([("mira isa dax", ("mira", "isa", "dax")), ("sam isa cat", ("sam", "isa", "cat"))])
    owns = induce([("ada owns box", ("ada", "owns", "box")), ("ned owns key", ("ned", "owns", "key"))])
    field, objects = [], ["green", "red", "mira", "dax"]
    add(field, "mira", "isa", "dax")
    add(field, "dax", "tail", "green")
    seq = discover(field, [("mira", "green")], objects)
    lines = [ln for ln in Path("data/dialogue.txt").read_text().splitlines() if ln.strip()]
    replies = [turn(field, objects, [isa, owns], seq, line) for line in lines]
    checks = {
        "found": seq == ("isa", "tail"),
        "orion_before": replies[7] == "orion has a green tail",
        "mira_before": replies[8] == "mira has a green tail",
        "orion_after": replies[10] == "orion has a red tail",
        "mira_after": replies[11] == "mira has a red tail",
        "unrelated": replies[12] == "rex owns key",
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {**checks, "seq": list(seq) if seq else None, "failed": failed, "claim": "color uses a found sequence; the question does not name it"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/chat_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    if "--interactive" in sys.argv:
        print("interactive needs a found sequence; use the script")
    else:
        run()
