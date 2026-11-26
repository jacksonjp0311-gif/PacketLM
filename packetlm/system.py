"""A small controller.

Given a question relation, find the operator that outputs it.
Apply that operator. Do not call a named procedure by hand.
Truth maintenance stays.
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

def answer(field, subject, want, objects):
    """Select an operator whose output relation is want, then apply it."""
    for op in operators(field):
        if op["o"] != want:
            continue
        first = op["s"]
        second = ask(field, first, "chain", objects) or first
        mid = ask(field, subject, first, objects)
        if not mid:
            continue
        val = ask(field, mid, second, objects)
        if val:
            return first, val
    return None

def run() -> dict:
    objects = [
        "bea", "cy", "dax", "cat", "blue", "green", "needle",
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
    # correct premise, drop nothing yet because we have not derived
    field = [f for f in field if not (f["s"] == "dax" and f["r"] == "tail")]
    add(field, "dax", "tail", "blue")
    save(FIELD, field)
    loaded = load(FIELD)
    hastail = answer(loaded, "mira", "hastail", objects)
    grand = answer(loaded, "ada", "grand", objects)
    missing = answer(loaded, "ada", "sibling", objects)
    checks = {
        "selected_hastail": hastail == ("isa", "blue"),
        "selected_grand": grand == ("parent", "kim"),
        "no_operator": missing is None,
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
        "hastail": hastail,
        "grand": grand,
        "failed": failed,
        "claim": "controller picks the operator by its output relation; not learned"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/system_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
