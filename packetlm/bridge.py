"""Questions read the field.

Statements write facts.
A question returns the derived answer or abstains.
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

def parse(sentence: str) -> tuple[str, str, str] | None:
    s = sentence.lower().strip().rstrip(".").rstrip("?")
    parts = s.split()
    if len(parts) >= 4 and parts[1] == "is" and parts[2] == "a":
        return norm(parts[0]), "isa", norm(parts[3])
    if len(parts) >= 4 and parts[1] == "have" and parts[-1] in {"tails", "tail"}:
        return norm(parts[0]), "tail", norm(parts[2])
    if len(parts) == 3 and parts[1] == "helps":
        return norm(parts[0]), "helps", norm(parts[2])
    if len(parts) >= 5 and parts[1] == "is" and parts[2] == "helped" and parts[3] == "by":
        return norm(parts[4]), "helps", norm(parts[0])
    return None

def ingest(field, sentence, objects):
    fact = parse(sentence)
    if not fact:
        return None
    s, r, o = fact
    for t in (s, r, o):
        if t not in objects:
            objects.append(t)
    add(field, s, r, o)
    return fact

def color_of(field, name, objects):
    kind = ask(field, name, "isa", objects)
    if not kind:
        return None
    return ask(field, kind, "tail", objects)

def ask_sentence(field, sentence, objects):
    s = sentence.lower().strip().rstrip("?")
    parts = s.split()
    if len(parts) >= 5 and parts[0] == "what" and parts[1] == "color" and parts[3] == "tail":
        name = norm(parts[4]) if parts[2] == "is" else norm(parts[2])
        # what color is mira tail / what color mira tail
        if "is" in parts:
            name = norm(parts[parts.index("is") + 1])
        color = color_of(field, name, objects)
        if not color:
            return {"abstain": True, "name": name}
        return {"abstain": False, "answer": f"{name} has a {color} tail"}
    return {"abstain": True, "reason": "unparsed"}

def run() -> dict:
    objects = []
    field = []
    for s in ["Mira is a dax.", "daxes have blue tails", "Alice helps Bob.", "Bob is helped by Alice."]:
        ingest(field, s, objects)
    before = ask_sentence(field, "what color is mira tail?", objects)
    field = [f for f in field if not (f["s"] == "dax" and f["r"] == "tail")]
    ingest(field, "daxes have green tails", objects)
    save(FIELD, field)
    loaded = load(FIELD)
    after = ask_sentence(loaded, "what color is mira tail?", objects)
    unknown = ask_sentence(loaded, "what color is orion tail?", objects)
    fly = ask_sentence(loaded, "can mira fly?", objects)
    checks = {
        "before_blue": before.get("answer") == "mira has a blue tail",
        "after_green": after.get("answer") == "mira has a green tail",
        "unknown_abstain": unknown.get("abstain") is True,
        "unparsed_abstain": fly.get("abstain") is True,
        "not_reversed": ask(loaded, "bob", "helps", objects) is None,
        "reloaded": len(loaded) == len(field),
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "before": before,
        "after": after,
        "unknown": unknown,
        "failed": failed,
        "claim": "question reads the field; unknown and unparsed abstain"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/bridge_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
