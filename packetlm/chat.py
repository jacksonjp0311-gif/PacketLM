"""Second session.

The constructions are saved.
The resumed answer uses those, not a fresh induce.
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
    resumed = turn(loaded["field"], loaded["objects"], loaded["library"], tuple(loaded["seq"]), "what color is orion tail")
    checks = {
        "found": seq == ("isa", "tail"),
        "missing_abstains": apply_seq(field, None, "orion", objects) is None,
        "orion_after": replies[10] == "orion has a red tail",
        "resumed_from_saved_library": resumed == "orion has a red tail",
        "library_saved": len(loaded.get("library", [])) == 2,
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {**checks, "failed": failed, "claim": "resume uses the saved constructions"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/chat_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

def interactive():
    state = load(STATE) if STATE.exists() else {"field": [], "objects": [], "seq": None, "library": fresh_library()}
    field, objects = state.get("field", []), state.get("objects", [])
    seq = tuple(state["seq"]) if state.get("seq") else None
    lib = state.get("library") or fresh_library()
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
