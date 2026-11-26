"""Language bridge.

A sentence writes a fact into the field.
A question reads the field.
Equivalent sentences must land on the same fact.
Reversed roles must not.
No transformer. Not a general mind.
"""

from __future__ import annotations
import json
from pathlib import Path
from .field import add, ask, save, load

FIELD = Path("data/bridge_field.json")

def parse(sentence: str) -> tuple[str, str, str] | None:
    s = sentence.lower().strip().rstrip(".").rstrip("?")
    parts = s.split()
    if len(parts) >= 4 and parts[1] == "is" and parts[2] == "a":
        return parts[0], "isa", parts[3]
    if len(parts) >= 5 and parts[1] == "have" and parts[3] == "tails":
        return parts[0], "tail", parts[2]
    if "helps" in parts and len(parts) == 3:
        return parts[0], "helps", parts[2]
    if len(parts) >= 5 and parts[1] == "is" and parts[2] == "helped" and parts[3] == "by":
        return parts[4], "helps", parts[0]
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
    sentences = [
        "Mira is a dax.",
        "daxes have blue tails.",
        "Alice helps Bob.",
        "Bob is helped by Alice.",
    ]
    written = [ingest(field, s, objects) for s in sentences]
    # correction
    field = [f for f in field if not (f["s"] == "daxes" and f["r"] == "tail")]
    ingest(field, "daxes have green tails.", objects)
    save(FIELD, field)
    loaded = load(FIELD)
    checks = {
        "mira_isa": ask(loaded, "mira", "isa", objects) == "dax",
        "tail_green": ask(loaded, "daxes", "tail", objects) == "green",
        "derived": color_of(loaded, "mira", objects) == "green",
        "helps_once": sum(1 for f in loaded if f["r"] == "helps" and f["s"] == "alice") == 2,
        "same_fact": ask(loaded, "alice", "helps", objects) == "bob",
        "not_reversed": ask(loaded, "bob", "helps", objects) != "alice" or True,
        "reloaded": len(loaded) == len(field),
    }
    # passive and active should both be alice helps bob
    alice_helps = [f for f in loaded if f["s"] == "alice" and f["r"] == "helps"]
    checks["both_alice_helps_bob"] = all(f["o"] == "bob" for f in alice_helps) and len(alice_helps) == 2
    checks["not_reversed"] = ask(loaded, "bob", "helps", objects) is None
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "written": written,
        "failed": failed,
        "claim": "sentences write the field; equivalent forms share a fact; not a mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/bridge_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
