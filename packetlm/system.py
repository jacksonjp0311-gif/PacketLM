"""Truth maintenance.

A derived fact records its premises.
If a premise changes, the derived fact is dropped and recomputed.
Older checks stay: ancestor, needle, sibling blocked, two operators.
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

def derive(field, a, out_rel, c, premises):
    add(field, a, out_rel, c)
    field[-1]["premises"] = premises
    field[-1]["derived"] = True

def invalidate(field, subject, relation):
    """Drop derived facts whose premises include this fact."""
    key = f"{subject}:{relation}"
    return [f for f in field if key not in f.get("premises", [])]

def apply_mixed(field, a, first_rel, objects):
    second = ask(field, first_rel, "chain", objects)
    out_rel = ask(field, first_rel, "compose", objects)
    if not second or not out_rel:
        return None
    b = ask(field, a, first_rel, objects)
    if not b:
        return None
    c = ask(field, b, second, objects)
    if not c:
        return None
    derive(field, a, out_rel, c, [f"{a}:{first_rel}", f"{b}:{second}"])
    return out_rel, c

def apply_same(field, a, mid_rel, objects):
    out_rel = ask(field, mid_rel, "compose", objects)
    if not out_rel:
        return None
    b = ask(field, a, mid_rel, objects)
    if not b:
        return None
    c = ask(field, b, mid_rel, objects)
    if not c:
        return None
    derive(field, a, out_rel, c, [f"{a}:{mid_rel}", f"{b}:{mid_rel}"])
    return out_rel, c

def run() -> dict:
    objects = [
        "bea", "cy", "dax", "cat", "blue", "green", "long", "needle",
        "parent", "grand", "sibling", "tail", "hastail", "jo", "kim",
    ]
    field = []
    for s, r, o in [
        ("ann", "ancestor", "bea"),
        ("bea", "ancestor", "cy"),
        ("dax", "tail", "green"),
        ("cat", "whiskers", "long"),
        ("mira", "isa", "dax"),
        ("sam", "isa", "cat"),
        ("lily", "found", "needle"),
        ("parent", "compose", "grand"),
        ("isa", "chain", "tail"),
        ("isa", "compose", "hastail"),
        ("ada", "parent", "jo"),
        ("jo", "parent", "kim"),
        ("ada", "sibling", "kim"),
    ]:
        add(field, s, r, o)
    parent_out = apply_same(field, "ada", "parent", objects)
    sibling = apply_same(field, "ada", "sibling", objects)
    mixed = apply_mixed(field, "mira", "isa", objects)
    before = ask(field, "mira", "hastail", objects)
    # correct the premise
    field = [f for f in field if not (f["s"] == "dax" and f["r"] == "tail")]
    add(field, "dax", "tail", "blue")
    field = invalidate(field, "dax", "tail")
    stale = ask(field, "mira", "hastail", objects)
    recomputed = apply_mixed(field, "mira", "isa", objects)
    save(FIELD, field)
    loaded = load(FIELD)
    checks = {
        "wrote_grand": parent_out == ("grand", "kim") and ask(loaded, "ada", "grand", objects) == "kim",
        "sibling_blocked": sibling is None,
        "before_green": before == "green",
        "stale_dropped": stale is None,
        "recomputed_blue": recomputed == ("hastail", "blue") and ask(loaded, "mira", "hastail", objects) == "blue",
        "sam_no_tail": apply_mixed(loaded, "sam", "isa", objects) is None,
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
        "claim": "derived fact dropped when its premise changed, then recomputed"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/system_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
