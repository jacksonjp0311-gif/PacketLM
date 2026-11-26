"""Cumulative bridge.

Every written token is registered before it is asked.
Question, correction, abstain, and learned owns stay.
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

def register(objects, *tokens):
    for t in tokens:
        if t not in objects:
            objects.append(t)

def write(field, objects, s, r, o):
    register(objects, s, r, o)
    add(field, s, r, o)

def learn_owns(examples):
    rels = set()
    for sent, (s, r, o) in examples:
        parts = sent.lower().split()
        if len(parts) != 3 or parts[0] != s or parts[2] != o:
            return None
        rels.add((parts[1], r))
    if len(rels) != 1 or len(examples) < 2:
        return None
    word, rel = next(iter(rels))
    return {"len": 3, "rel_at": 1, "word": word, "rel": rel}

def apply_pattern(pattern, sentence):
    if not pattern:
        return None
    parts = sentence.lower().strip().rstrip(".").split()
    if len(parts) != pattern["len"] or parts[pattern["rel_at"]] != pattern["word"]:
        return None
    return norm(parts[0]), pattern["rel"], norm(parts[2])

def via_operator(field, name, objects):
    if ask(field, "isa", "compose", objects) != "hastail":
        return None
    if ask(field, "isa", "chain", objects) != "tail":
        return None
    kind = ask(field, name, "isa", objects)
    if not kind:
        return None
    return ask(field, kind, "tail", objects)

def ask_color(field, sentence, objects):
    parts = sentence.lower().strip().rstrip("?").split()
    if len(parts) == 5 and parts[0] == "what" and parts[1] == "color" and parts[2] == "is" and parts[-1] == "tail":
        name = norm(parts[3])
        color = via_operator(field, name, objects)
        if not color:
            return {"abstain": True, "reason": "unknown", "name": name}
        return {"abstain": False, "answer": f"{name} has a {color} tail"}
    return {"abstain": True, "reason": "unparsed"}

def run() -> dict:
    objects = []
    field = []
    write(field, objects, "isa", "chain", "tail")
    write(field, objects, "isa", "compose", "hastail")
    write(field, objects, "mira", "isa", "dax")
    write(field, objects, "dax", "tail", "blue")
    before = ask_color(field, "what color is mira tail?", objects)
    field = [f for f in field if not (f["s"] == "dax" and f["r"] == "tail")]
    write(field, objects, "dax", "tail", "green")
    pattern = learn_owns([
        ("ada owns box", ("ada", "owns", "box")),
        ("ned owns key", ("ned", "owns", "key")),
    ])
    unseen = apply_pattern(pattern, "rex owns map")
    if unseen:
        write(field, objects, *unseen)
    bad = apply_pattern(pattern, "rex holds map")
    save(FIELD, field)
    loaded = load(FIELD)
    after = ask_color(loaded, "what color is mira tail?", objects)
    unknown = ask_color(loaded, "what color is orion tail?", objects)
    fly = ask_color(loaded, "can mira fly?", objects)
    checks = {
        "before_blue": before.get("answer") == "mira has a blue tail",
        "after_green": after.get("answer") == "mira has a green tail",
        "unknown_reason": unknown.get("reason") == "unknown",
        "unparsed_reason": fly.get("reason") == "unparsed",
        "learned": pattern is not None and pattern["rel"] == "owns",
        "unseen_owns": unseen == ("rex", "owns", "map") and ask(loaded, "rex", "owns", objects) == "map",
        "holds_rejected": bad is None,
        "reloaded": len(loaded) == len(field),
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "failed": failed,
        "claim": "every written token is registered; prior checks remain"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/bridge_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
