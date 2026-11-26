"""Controller plus truth maintenance.

The question selects the operator.
A derived fact records premises.
A premise change drops the derived fact.
Not a general mind.
"""

from __future__ import annotations
import json
from pathlib import Path
from .field import add, ask, save, load
from .packets import hash_to_bits
from .router import Router

FIELD = Path("data/system_field.json")

def walk(field, start, relation, objects, steps=3):
    out, cur = [], start
    for _ in range(steps):
        nxt = ask(field, cur, relation, objects)
        if not nxt:
            break
        out.append(nxt)
        cur = nxt
    return out

def operators(field):
    return [f for f in field if f["r"] == "compose"]

def derive(field, a, out_rel, c, premises):
    add(field, a, out_rel, c)
    field[-1]["premises"] = premises
    field[-1]["derived"] = True

def invalidate(field, subject, relation):
    key = f"{subject}:{relation}"
    return [f for f in field if key not in f.get("premises", [])]

def answer(field, subject, want, objects, write=False):
    for op in operators(field):
        if op["o"] != want:
            continue
        first = op["s"]
        second = ask(field, first, "chain", objects) or first
        mid = ask(field, subject, first, objects)
        if not mid:
            continue
        val = ask(field, mid, second, objects)
        if not val:
            continue
        if write:
            derive(field, subject, want, val, [f"{subject}:{first}", f"{mid}:{second}"])
        return first, val
    return None

def run() -> dict:
    objects = [
        "bea", "cy", "dax", "green", "blue", "needle",
        "parent", "grand", "tail", "hastail", "jo", "kim",
    ]
    field = []
    for s, r, o in [
        ("ann", "ancestor", "bea"),
        ("bea", "ancestor", "cy"),
        ("dax", "tail", "green"),
        ("mira", "isa", "dax"),
        ("lily", "found", "needle"),
        ("parent", "compose", "grand"),
        ("isa", "chain", "tail"),
        ("isa", "compose", "hastail"),
        ("ada", "parent", "jo"),
        ("jo", "parent", "kim"),
    ]:
        add(field, s, r, o)
    written = answer(field, "mira", "hastail", objects, write=True)
    before = ask(field, "mira", "hastail", objects)
    field = [f for f in field if not (f["s"] == "dax" and f["r"] == "tail")]
    add(field, "dax", "tail", "blue")
    field = invalidate(field, "dax", "tail")
    stale = ask(field, "mira", "hastail", objects)
    save(FIELD, field)
    loaded = load(FIELD)
    again = answer(loaded, "mira", "hastail", objects)
    checks = {
        "selected_and_wrote": written == ("isa", "green") and before == "green",
        "stale_dropped": stale is None,
        "reselected_blue": again == ("isa", "blue"),
        "selected_grand": answer(loaded, "ada", "grand", objects) == ("parent", "kim"),
        "no_sibling_op": answer(loaded, "ada", "sibling", objects) is None,
        "derived_cy": walk(loaded, "ann", "ancestor", objects) == ["bea", "cy"],
        "retained": ask(loaded, "lily", "found", objects) == "needle",
        "reloaded": len(loaded) == len(field),
        "tight_won": Router(
            [hash_to_bits("lily needle"), hash_to_bits("lily needle river stones dusk")]
        ).select(hash_to_bits("lily needle"), 1)[0][0].bits == hash_to_bits("lily needle").bits,
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "failed": failed,
        "claim": "controller selects; derived fact dies with its premise; not a mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/system_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
