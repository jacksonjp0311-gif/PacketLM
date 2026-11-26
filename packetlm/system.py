"""G39 start.

Invalidate recursively.
Derived facts name the operator.
Missing chain abstains. No silent same-relation fallback.
Two examples of r1 then r2 writing r3 induce the operator.
A third pair must use it. A negative must not.
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

def derive(field, a, out_rel, c, premises, op):
    add(field, a, out_rel, c)
    field[-1]["premises"] = premises + [f"op:{op}"]
    field[-1]["derived"] = True
    field[-1]["id"] = f"{a}:{out_rel}"

def invalidate(field, key, seen=None):
    seen = seen or set()
    if key in seen:
        return field
    seen.add(key)
    victims = [f for f in field if key in f.get("premises", [])]
    field = [f for f in field if key not in f.get("premises", [])]
    for v in victims:
        field = invalidate(field, v.get("id", ""), seen)
    return field

def induce(field, examples):
    """examples: (a, r1, b, r2, c, r3). If two share r1,r2,r3, store the operator."""
    from collections import Counter
    keys = Counter((r1, r2, r3) for _, r1, _, r2, _, r3 in examples)
    for (r1, r2, r3), n in keys.items():
        if n >= 2 and not ask(field, r1, "compose", [r3]):
            add(field, r1, "chain", r2)
            add(field, r1, "compose", r3)
            return r1, r2, r3
    return None

def answer(field, subject, want, objects):
    for op in [f for f in field if f["r"] == "compose" and f["o"] == want]:
        first = op["s"]
        second = ask(field, first, "chain", objects)
        if not second:
            continue
        mid = ask(field, subject, first, objects)
        if not mid:
            continue
        val = ask(field, mid, second, objects)
        if val:
            return first, val
    return None

def run() -> dict:
    objects = ["bea", "cy", "needle", "p", "q", "g", "a", "b", "c", "d", "e", "f", "x", "y", "z"]
    field = []
    for s, r, o in [
        ("ann", "ancestor", "bea"),
        ("bea", "ancestor", "cy"),
        ("lily", "found", "needle"),
    ]:
        add(field, s, r, o)
    examples = [
        ("a", "p", "b", "p", "c", "g"),
        ("d", "p", "e", "p", "f", "g"),
    ]
    for a, r1, b, r2, c, r3 in examples:
        add(field, a, r1, b)
        add(field, b, r2, c)
        derive(field, a, r3, c, [f"{a}:{r1}", f"{b}:{r2}"], f"{r1}+{r2}")
    induced = induce(field, examples)
    # unseen pair
    add(field, "x", "p", "y")
    add(field, "y", "p", "z")
    unseen = answer(field, "x", "g", objects)
    # negative: no second hop
    add(field, "no", "p", "one")
    neg = answer(field, "no", "g", objects)
    # recursive: derived depends on induced conclusion
    derive(field, "x", "far", "z", ["x:g"], "g")
    field = invalidate(field, "x:p")
    stale = ask(field, "x", "g", objects)
    far = ask(field, "x", "far", objects)
    save(FIELD, field)
    loaded = load(FIELD)
    checks = {
        "induced": induced == ("p", "p", "g"),
        "unseen": unseen == ("p", "z"),
        "negative": neg is None,
        "stale_dropped": stale is None,
        "recursive_dropped": far is None,
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
        "induced": induced,
        "failed": failed,
        "claim": "operator induced from two examples; recursive invalidate; not a mind"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/system_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
