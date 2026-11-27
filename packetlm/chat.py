"""Causal.

A new sentence is interpreted with the saved library.
The same sentence with an empty library abstains.
No fallback rebuild.
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
            if not ok or cur != expected:
                ok = False
            if not ok:
                break
        if ok:
            hits.append(seq)
    return hits[0] if len(hits) == 1 else None

def apply_seq(field, seq, subject, objects):
    if not seq:
        return None
    cur = subject
    for rel in seq:
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

def fresh_library():
    return [
        induce([("mira isa dax", ("mira", "isa", "dax")), ("sam isa cat", ("sam", "isa", "cat"))]),
        induce([("ada owns box", ("ada", "owns", "box")), ("ned owns key", ("ned", "owns", "key"))]),
    ]

def run() -> dict:
    field, objects = [], ["green", "red", "mira", "dax"]
    add(field, "mira", "isa", "dax")
    add(field, "dax", "tail", "green")
    seq = discover(field, [("mira", "green")], objects)
    lib = fresh_library()
    lines = [ln for ln in Path("data/dialogue.txt").read_text().splitlines() if ln.strip()]
    replies = [turn(field, objects, lib, seq, line) for line in lines]
    save(STATE, {"field": field, "objects": objects, "seq": list(seq) if seq else None, "library": lib})
    loaded = load(STATE)
    with_lib = turn(list(loaded["field"]), list(loaded["objects"]), loaded["library"], tuple(loaded["seq"]), "luna isa dax")
    without = turn(list(loaded["field"]), list(loaded["objects"]), [], tuple(loaded["seq"]), "luna isa dax")
    checks = {
        "found": seq == ("isa", "tail"),
        "orion_after": replies[10] == "orion has a red tail",
        "saved_interprets": with_lib == "recorded luna isa dax",
        "ablated_abstains": without == "unparsed",
        "no_fallback": without != with_lib,
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {**checks, "failed": failed, "claim": "saved construction is required; empty library abstains"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/chat_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

def interactive():
    state = load(STATE) if STATE.exists() else {"field": [], "objects": [], "seq": None, "library": []}
    field, objects = state.get("field", []), state.get("objects", [])
    seq = tuple(state["seq"]) if state.get("seq") else None
    lib = state.get("library") or []
    while True:
        try:
            line = input("> ")
        except EOFError:
            break
        if line.strip() in {"quit", "exit"}:
            break
        print(turn(field, objects, lib, seq, line))
        save(STATE, {"field": field, "objects": objects, "seq": list(seq) if seq else None, "library": lib})

if __name__ == "__main__":
    if "--interactive" in sys.argv:
        interactive()
    else:
        run()
