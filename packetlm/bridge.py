"""Learn a construction.

Two labeled examples of 'X owns Y' induce a pattern.
A third sentence uses it.
The isa operator path and correction stay.
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

def learn_owns(examples: list[tuple[str, tuple[str, str, str]]]) -> dict | None:
    """examples: ('ada owns box', ('ada','owns','box')). Pattern is word 1 = relation."""
    rels = set()
    for sent, (s, r, o) in examples:
        parts = sent.lower().split()
        if len(parts) != 3 or parts[0] != s or parts[2] != o:
            return None
        rels.add((parts[1], r))
    if len(rels) != 1:
        return None
    word, rel = next(iter(rels))
    return {"len": 3, "rel_at": 1, "word": word, "rel": rel}

def apply_pattern(pattern, sentence):
    parts = sentence.lower().strip().rstrip(".").split()
    if not pattern or len(parts) != pattern["len"] or parts[pattern["rel_at"]] != pattern["word"]:
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

def run() -> dict:
    objects = ["hastail", "tail", "isa", "owns"]
    field = []
    add(field, "isa", "chain", "tail")
    add(field, "isa", "compose", "hastail")
    add(field, "mira", "isa", "dax")
    add(field, "dax", "tail", "green")
    examples = [
        ("ada owns box", ("ada", "owns", "box")),
        ("ned owns key", ("ned", "owns", "key")),
    ]
    pattern = learn_owns(examples)
    unseen = apply_pattern(pattern, "rex owns map")
    if unseen:
        add(field, *unseen)
    bad = apply_pattern(pattern, "rex holds map")
    save(FIELD, field)
    loaded = load(FIELD)
    checks = {
        "learned": pattern is not None and pattern["rel"] == "owns",
        "unseen_owns": unseen == ("rex", "owns", "map") and ask(loaded, "rex", "owns", objects) == "map",
        "holds_rejected": bad is None,
        "mira_green": via_operator(loaded, "mira", objects) == "green",
        "reloaded": len(loaded) == len(field),
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "pattern": pattern,
        "failed": failed,
        "claim": "owns learned from two examples; holds rejected; isa path still works"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/bridge_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
