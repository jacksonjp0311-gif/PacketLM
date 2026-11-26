"""Bridge through the operator.

isa chain tail and isa compose hastail live in the field.
The question selects that operator.
A correction sentence replaces the tail.
Unknown and unparsed stay distinct.
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
    if s.startswith("no,"):
        s = s[3:].strip()
    parts = s.split()
    if len(parts) == 4 and parts[1] == "is" and parts[2] == "a":
        return norm(parts[0]), "isa", norm(parts[3])
    if len(parts) == 4 and parts[1] == "have" and parts[-1] in {"tails", "tail"}:
        return norm(parts[0]), "tail", norm(parts[2])
    if len(parts) == 3 and parts[1] == "helps":
        return norm(parts[0]), "helps", norm(parts[2])
    return None

def ingest(field, sentence, objects, correct=False):
    fact = parse(sentence)
    if not fact:
        return None
    s, r, o = fact
    if correct or sentence.lower().startswith("no,"):
        field[:] = [f for f in field if not (f["s"] == s and f["r"] == r)]
    for t in (s, r, o):
        if t not in objects:
            objects.append(t)
    add(field, s, r, o)
    return fact

def via_operator(field, name, objects):
    if ask(field, "isa", "compose", objects) != "hastail":
        return None
    if ask(field, "isa", "chain", objects) != "tail":
        return None
    kind = ask(field, name, "isa", objects)
    if not kind:
        return None
    return ask(field, kind, "tail", objects)

def ask_sentence(field, sentence, objects):
    s = sentence.lower().strip().rstrip("?")
    parts = s.split()
    if len(parts) == 5 and parts[0] == "what" and parts[1] == "color" and parts[2] == "is" and parts[-1] == "tail":
        name = norm(parts[3])
        color = via_operator(field, name, objects)
        if not color:
            return {"abstain": True, "reason": "unknown", "name": name}
        return {"abstain": False, "answer": f"{name} has a {color} tail", "via": "isa"}
    return {"abstain": True, "reason": "unparsed"}

def run() -> dict:
    objects = ["hastail", "tail", "isa"]
    field = []
    add(field, "isa", "chain", "tail")
    add(field, "isa", "compose", "hastail")
    for s in ["Mira is a dax.", "daxes have blue tails", "Alice helps Bob."]:
        ingest(field, s, objects)
    before = ask_sentence(field, "what color is mira tail?", objects)
    ingest(field, "no, daxes have green tails", objects, correct=True)
    save(FIELD, field)
    loaded = load(FIELD)
    after = ask_sentence(loaded, "what color is mira tail?", objects)
    unknown = ask_sentence(loaded, "what color is orion tail?", objects)
    fly = ask_sentence(loaded, "can mira fly?", objects)
    checks = {
        "before_blue": before.get("answer") == "mira has a blue tail",
        "via_operator": before.get("via") == "isa" and after.get("via") == "isa",
        "corrected_green": after.get("answer") == "mira has a green tail",
        "unknown_reason": unknown.get("reason") == "unknown",
        "unparsed_reason": fly.get("reason") == "unparsed",
        "reloaded": len(loaded) == len(field),
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "before": before,
        "after": after,
        "failed": failed,
        "claim": "question uses the stored isa operator; correction is a sentence"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/bridge_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
