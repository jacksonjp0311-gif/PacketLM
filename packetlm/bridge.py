"""Passive without losing the suite.

'Y helped-by X' learns to write X helps Y.
Blue to green, owns, and isa stay.
Not a general mind.
"""

from __future__ import annotations
import json
from pathlib import Path
from .field import add, ask, save, load

FIELD = Path("data/bridge_field.json")

def write(field, objects, s, r, o):
    for t in (s, r, o):
        if t not in objects:
            objects.append(t)
    add(field, s, r, o)

def learn_svo(examples, word, rel):
    if len(examples) < 2:
        return None
    for sent, (s, r, o) in examples:
        parts = sent.lower().split()
        if len(parts) != 3 or parts[0] != s or parts[1] != word or parts[2] != o or r != rel:
            return None
    return {"word": word, "rel": rel, "flip": False}

def learn_passive(examples):
    """'bob by alice' -> alice helps bob. Object is first, subject is last."""
    if len(examples) < 2:
        return None
    for sent, (s, r, o) in examples:
        parts = sent.lower().split()
        if parts != [o, "by", s] or r != "helps":
            return None
    return {"word": "by", "rel": "helps", "flip": True}

def apply_pattern(pattern, sentence):
    if not pattern:
        return None
    parts = sentence.lower().strip().rstrip(".").split()
    if pattern["flip"]:
        if len(parts) != 3 or parts[1] != "by":
            return None
        return parts[2], pattern["rel"], parts[0]
    if len(parts) != 3 or parts[1] != pattern["word"]:
        return None
    return parts[0], pattern["rel"], parts[2]

def via_operator(field, name, objects):
    if ask(field, "isa", "compose", objects) != "hastail" or ask(field, "isa", "chain", objects) != "tail":
        return None
    kind = ask(field, name, "isa", objects)
    if not kind:
        return None
    return ask(field, kind, "tail", objects)

def run() -> dict:
    objects = []
    field = []
    write(field, objects, "isa", "chain", "tail")
    write(field, objects, "isa", "compose", "hastail")
    write(field, objects, "dax", "tail", "blue")
    owns = learn_svo([
        ("ada owns box", ("ada", "owns", "box")),
        ("ned owns key", ("ned", "owns", "key")),
    ], "owns", "owns")
    isa = learn_svo([
        ("sam isa cat", ("sam", "isa", "cat")),
        ("lee isa bird", ("lee", "isa", "bird")),
    ], "isa", "isa")
    passive = learn_passive([
        ("bob by alice", ("alice", "helps", "bob")),
        ("kim by ada", ("ada", "helps", "kim")),
    ])
    if owns:
        write(field, objects, "owns", "pattern", "svo")
    if isa:
        write(field, objects, "isa", "pattern", "svo")
    if passive:
        write(field, objects, "by", "pattern", "passive")
    for fact in [
        apply_pattern(isa, "mira isa dax"),
        apply_pattern(isa, "orion isa dax"),
        apply_pattern(owns, "rex owns map"),
        apply_pattern(passive, "lee by ned"),
    ]:
        if fact:
            write(field, objects, *fact)
    before = {n: via_operator(field, n, objects) for n in ("mira", "orion")}
    field = [f for f in field if not (f["s"] == "dax" and f["r"] == "tail")]
    write(field, objects, "dax", "tail", "green")
    save(FIELD, field)
    final = load(FIELD)
    after = {n: via_operator(final, n, objects) for n in ("mira", "orion")}
    checks = {
        "before_blue": before == {"mira": "blue", "orion": "blue"},
        "after_green": after == {"mira": "green", "orion": "green"},
        "owns_kept": ask(final, "rex", "owns", objects) == "map",
        "passive_applied": ask(final, "ned", "helps", objects) == "lee",
        "not_reversed": ask(final, "lee", "helps", objects) is None,
        "isa_applied": ask(final, "mira", "isa", objects) == "dax",
        "reloaded": len(final) == len(field),
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {**checks, "failed": failed, "claim": "passive added; correction and owns retained"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/bridge_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
