"""Passive restored from the field.

The suite stays: blue to green, owns, isa, not reversed.
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
    if len(examples) < 2:
        return None
    for sent, (s, r, o) in examples:
        if sent.lower().split() != [o, "by", s] or r != "helps":
            return None
    return {"word": "by", "rel": "helps", "flip": True}

def from_field(field, objects, word, flip):
    mark = "passive" if flip else "svo"
    if ask(field, word, "pattern", objects) != mark:
        return None
    return {"word": word, "rel": word if not flip else "helps", "flip": flip}

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
    if learn_svo([("ada owns box", ("ada", "owns", "box")), ("ned owns key", ("ned", "owns", "key"))], "owns", "owns"):
        write(field, objects, "owns", "pattern", "svo")
    if learn_svo([("sam isa cat", ("sam", "isa", "cat")), ("lee isa bird", ("lee", "isa", "bird"))], "isa", "isa"):
        write(field, objects, "isa", "pattern", "svo")
    if learn_passive([("bob by alice", ("alice", "helps", "bob")), ("kim by ada", ("ada", "helps", "kim"))]):
        write(field, objects, "by", "pattern", "passive")
    save(FIELD, field)
    loaded = load(FIELD)
    owns_p = from_field(loaded, objects, "owns", False)
    isa_p = from_field(loaded, objects, "isa", False)
    by_p = from_field(loaded, objects, "by", True)
    for fact in [
        apply_pattern(isa_p, "mira isa dax"),
        apply_pattern(isa_p, "orion isa dax"),
        apply_pattern(owns_p, "rex owns map"),
        apply_pattern(by_p, "lee by ned"),
    ]:
        if fact:
            write(loaded, objects, *fact)
    before = {n: via_operator(loaded, n, objects) for n in ("mira", "orion")}
    loaded = [f for f in loaded if not (f["s"] == "dax" and f["r"] == "tail")]
    write(loaded, objects, "dax", "tail", "green")
    save(FIELD, loaded)
    final = load(FIELD)
    after = {n: via_operator(final, n, objects) for n in ("mira", "orion")}
    checks = {
        "before_blue": before == {"mira": "blue", "orion": "blue"},
        "after_green": after == {"mira": "green", "orion": "green"},
        "owns_kept": ask(final, "rex", "owns", objects) == "map",
        "passive_from_field": ask(final, "ned", "helps", objects) == "lee",
        "not_reversed": ask(final, "lee", "helps", objects) is None,
        "isa_applied": ask(final, "mira", "isa", objects) == "dax",
        "reloaded": final == loaded and len(final) == len(loaded),  # was the constant True (G44 audit item 11)
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {**checks, "failed": failed, "claim": "passive applied from reloaded field; suite retained"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/bridge_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
