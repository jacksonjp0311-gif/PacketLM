"""Language bridge.

Sentences write the field.
Plurals normalize so daxes and dax are one type.
A question reads the field and speaks a short answer.
Equivalent forms share a fact. Reversed roles do not.
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
    if len(parts) >= 5 and parts[1] == "have" and parts[3] == "tails":
        return norm(parts[0]), "tail", norm(parts[2])
    if "helps" in parts and len(parts) == 3:
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

def speak(name, color) -> str | None:
    if not color:
        return None
    return f"{name} has a {color} tail"

def run() -> dict:
    objects = []
    field = []
    for s in [
        "Mira is a dax.",
        "daxes have blue tails.",
        "Alice helps Bob.",
        "Bob is helped by Alice.",
    ]:
        ingest(field, s, objects)
    before = color_of(field, "mira", objects)
    field = [f for f in field if not (f["s"] == "dax" and f["r"] == "tail")]
    ingest(field, "daxes have green tails.", objects)
    save(FIELD, field)
    loaded = load(FIELD)
    after = color_of(loaded, "mira", objects)
    alice_helps = [f for f in loaded if f["s"] == "alice" and f["r"] == "helps"]
    checks = {
        "before_blue": before == "blue",
        "after_green": after == "green",
        "spoke": speak("mira", after) == "mira has a green tail",
        "both_alice_helps_bob": len(alice_helps) == 2 and all(f["o"] == "bob" for f in alice_helps),
        "not_reversed": ask(loaded, "bob", "helps", objects) is None,
        "reloaded": len(loaded) == len(field),
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "answer": speak("mira", after),
        "failed": failed,
        "claim": "plural normalized; answer spoken from the field; not a mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/bridge_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
