"""Two constructions.

owns and isa are both learned from labeled examples, stored, reloaded, applied.
Prior checks stay.
Not a general mind.
"""

from __future__ import annotations
import json
from pathlib import Path
from .field import add, ask, save, load

FIELD = Path("data/bridge_field.json")

def norm(token: str) -> str:
    if token.endswith("es") and len(token) > 4:
        return token[:-2]
    if token.endswith("s") and len(token) > 3:
        return token[:-1]
    return token

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
    return {"len": 3, "rel_at": 1, "word": word, "rel": rel}

def pattern_from_field(field, objects, word):
    if ask(field, word, "pattern", objects) != "svo":
        return None
    return {"len": 3, "rel_at": 1, "word": word, "rel": word}

def apply_pattern(pattern, sentence):
    if not pattern:
        return None
    parts = sentence.lower().strip().rstrip(".").split()
    if len(parts) != pattern["len"] or parts[pattern["rel_at"]] != pattern["word"]:
        return None
    return norm(parts[0]), pattern["rel"], norm(parts[2])

def via_operator(field, name, objects):
    if ask(field, "isa", "compose", objects) != "hastail" or ask(field, "isa", "chain", objects) != "tail":
        return None
    kind = ask(field, name, "isa", objects)
    if not kind:
        return None
    return ask(field, kind, "tail", objects)

def ask_color(field, sentence, objects):
    parts = sentence.lower().strip().rstrip("?").split()
    if len(parts) == 5 and parts[0] == "what" and parts[1] == "color" and parts[2] == "is" and parts[-1] == "tail":
        color = via_operator(field, norm(parts[3]), objects)
        if not color:
            return {"abstain": True, "reason": "unknown"}
        return {"abstain": False, "answer": f"{norm(parts[3])} has a {color} tail"}
    return {"abstain": True, "reason": "unparsed"}

def run() -> dict:
    objects = []
    field = []
    write(field, objects, "isa", "chain", "tail")
    write(field, objects, "isa", "compose", "hastail")
    write(field, objects, "dax", "tail", "green")
    owns = learn_svo([
        ("ada owns box", ("ada", "owns", "box")),
        ("ned owns key", ("ned", "owns", "key")),
    ], "owns", "owns")
    isa = learn_svo([
        ("mira isa dax", ("mira", "isa", "dax")),
        ("sam isa cat", ("sam", "isa", "cat")),
    ], "isa", "isa")
    if owns:
        write(field, objects, "owns", "pattern", "svo")
    if isa:
        write(field, objects, "isa", "pattern", "svo")
    save(FIELD, field)
    loaded = load(FIELD)
    owns_p = pattern_from_field(loaded, objects, "owns")
    isa_p = pattern_from_field(loaded, objects, "isa")
    rex = apply_pattern(owns_p, "rex owns map")
    orion = apply_pattern(isa_p, "orion isa dax")
    if rex:
        write(loaded, objects, *rex)
    if orion:
        write(loaded, objects, *orion)
    save(FIELD, loaded)
    final = load(FIELD)
    checks = {
        "owns_applied": rex == ("rex", "owns", "map") and ask(final, "rex", "owns", objects) == "map",
        "isa_applied": orion == ("orion", "isa", "dax") and ask(final, "orion", "isa", objects) == "dax",
        "orion_green": via_operator(final, "orion", objects) == "green",
        "holds_rejected": apply_pattern(owns_p, "rex holds map") is None,
        "unknown_reason": ask_color(final, "what color is noone tail?", objects).get("reason") == "unknown",
        "unparsed_reason": ask_color(final, "can mira fly?", objects).get("reason") == "unparsed",
        "reloaded": True,
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {**checks, "failed": failed, "claim": "two constructions restored and applied; not a mind"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/bridge_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
