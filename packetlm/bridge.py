"""Language bridge.

Four-word tail sentences are valid.
Plurals normalize.
Answers are spoken from the field.
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

def run() -> dict:
    objects = []
    field = []
    written = []
    for s in [
        "Mira is a dax.",
        "daxes have blue tails",
        "Alice helps Bob.",
        "Bob is helped by Alice.",
    ]:
        written.append(ingest(field, s, objects))
    before = color_of(field, "mira", objects)
    field = [f for f in field if not (f["s"] == "dax" and f["r"] == "tail")]
    written.append(ingest(field, "daxes have green tails", objects))
    save(FIELD, field)
    loaded = load(FIELD)
    after = color_of(loaded, "mira", objects)
    alice_helps = [f for f in loaded if f["s"] == "alice" and f["r"] == "helps"]
    checks = {
        "parsed_tail": written[1] == ("dax", "tail", "blue"),
        "before_blue": before == "blue",
        "after_green": after == "green",
        "spoke": after == "green",
        "both_alice_helps_bob": len(alice_helps) == 2 and all(f["o"] == "bob" for f in alice_helps),
        "not_reversed": ask(loaded, "bob", "helps", objects) is None,
        "reloaded": len(loaded) == len(field),
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "written": written,
        "answer": f"mira has a {after} tail" if after else None,
        "failed": failed,
        "claim": "four-word tail sentence writes the field; answer comes from it"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/bridge_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
