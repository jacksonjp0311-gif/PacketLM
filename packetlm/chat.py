"""Labels from examples.

The example says the asked word and the spoken relation.
The search finds the path.
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

def choose(library, meaning):
    hits = [c for c in library if c and c.get("meaning") == meaning]
    return hits[0] if len(hits) == 1 else None

def express(construction, fact):
    if not construction:
        return None
    s, r, o = fact
    roles = {"s": s, "r": construction["word"], "o": o}
    return " ".join(roles[role] for role in construction["order"])

def acquire(field, objects, labeled):
    operators = []
    for subject, asked, expected, out in labeled:
        seq = discover(field, [(subject, expected)], objects)
        if seq:
            operators.append({"in": asked, "seq": list(seq), "out": out})
    return operators

def turn(field, objects, library, operators, line):
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
    if len(parts) == 4 and parts[0] == "what" and parts[1] == "is":
        op = next((o for o in operators if o["in"] == parts[3]), None)
        if not op:
            return "unknown"
        value = apply_seq(field, tuple(op["seq"]), parts[2], objects)
        spoken = express(choose(library, op["out"]), (parts[2], op["out"], value)) if value else None
        return spoken or "unknown"
    if len(parts) == 4 and parts[0] == "what" and parts[1] == "does" and parts[3] == "own":
        owned = ask(field, parts[2], "owns", objects)
        return f"{parts[2]} owns {owned}" if owned else "unknown"
    return "unparsed"

def fresh_library():
    return [
        induce([("mira isa dax", ("mira", "isa", "dax")), ("sam isa cat", ("sam", "isa", "cat"))]),
        induce([("ada owns box", ("ada", "owns", "box")), ("ned owns key", ("ned", "owns", "key"))]),
        induce([("mira hastail green", ("mira", "hastail", "green")), ("sam hastail blue", ("sam", "hastail", "blue"))]),
        induce([("mira at dock", ("mira", "at", "dock")), ("sam at bay", ("sam", "at", "bay"))]),
    ]

def run() -> dict:
    field, objects = [], ["green", "red", "mira", "dax", "lab", "dock"]
    add(field, "mira", "isa", "dax")
    add(field, "dax", "tail", "green")
    add(field, "mira", "in", "lab")
    add(field, "lab", "at", "dock")
    operators = acquire(field, objects, [
        ("mira", "tail", "green", "hastail"),
        ("mira", "location", "dock", "at"),
    ])
    lib = fresh_library()
    lines = [ln for ln in Path("data/dialogue.txt").read_text().splitlines() if ln.strip()]
    replies = [turn(field, objects, lib, operators, line) for line in lines]
    save(STATE, {"field": field, "objects": objects, "operators": operators, "library": lib})
    loaded = load(STATE)
    checks = {
        "two": [o["in"] for o in operators] == ["tail", "location"],
        "tail": turn(list(loaded["field"]), list(loaded["objects"]), loaded["library"], loaded["operators"], "what is orion tail") == "orion hastail red",
        "location": turn(list(loaded["field"]), list(loaded["objects"]), loaded["library"], loaded["operators"], "what is mira location") == "mira at dock",
        "age_abstains": turn(list(loaded["field"]), list(loaded["objects"]), loaded["library"], loaded["operators"], "what is orion age") == "unknown",
        "generic": replies[7] == "orion hastail green",
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {**checks, "failed": failed, "claim": "operators built from examples; the asked word picks"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/chat_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

def interactive():
    state = load(STATE) if STATE.exists() else {"field": [], "objects": [], "operators": [], "library": []}
    field, objects = state.get("field", []), state.get("objects", [])
    operators, lib = state.get("operators") or [], state.get("library") or []
    while True:
        try:
            line = input("> ")
        except EOFError:
            break
        if line.strip() in {"quit", "exit"}:
            break
        print(turn(field, objects, lib, operators, line))
        save(STATE, {"field": field, "objects": objects, "operators": operators, "library": lib})

if __name__ == "__main__":
    if "--interactive" in sys.argv:
        interactive()
    else:
        run()
