"""Autonomous step.

The environment holds the rule.
The learner picks a subject where the paths disagree.
It asks. One path dies.
Not a general mind.
"""

from __future__ import annotations
import json
from pathlib import Path
from .field import add, ask

def candidates(field, examples, objects):
    rels = sorted({f["r"] for f in field})
    out_rels = {out for _, out, _ in examples}
    if len(out_rels) != 1:
        return []
    out_rel = next(iter(out_rels))
    hits = []
    for first in rels:
        for second in rels:
            if all(
                ask(field, ask(field, s, first, objects) or "", second, objects) == expected
                for s, _, expected in examples
            ):
                hits.append((first, second, out_rel))
    return hits

def discover(field, examples, objects):
    hits = candidates(field, examples, objects)
    return hits[0] if len(hits) == 1 else None

def apply_path(field, path, subject, objects):
    if not path:
        return None
    first, second, _ = path
    mid = ask(field, subject, first, objects)
    return ask(field, mid, second, objects) if mid else None

def pick(field, paths, subjects, objects):
    for s in subjects:
        preds = {apply_path(field, p, s, objects) for p in paths}
        preds.discard(None)
        if len(preds) > 1:
            return s
    return None

def run() -> dict:
    # hidden rule: p then p
    env = []
    for s, r, o in [
        ("x", "p", "y"), ("y", "p", "z"),
        ("x", "q", "a"), ("a", "q", "z"),
        ("m", "p", "n"), ("n", "p", "w"),
        ("m", "q", "b"), ("b", "q", "nope"),
        ("hold", "p", "mid"), ("mid", "p", "yes"),
    ]:
        add(env, s, r, o)
    objects = ["x", "y", "z", "a", "m", "n", "w", "b", "nope", "hold", "mid", "yes"]
    live = candidates(env, [("x", "out", "z")], objects)
    chosen = pick(env, live, ["m", "hold"], objects)
    answer = apply_path(env, ("p", "p", "out"), chosen, objects) if chosen else None
    after = candidates(env, [("x", "out", "z"), (chosen, "out", answer)], objects) if chosen else []
    qualified = apply_path(env, after[0], "hold", objects) if len(after) == 1 else None
    checks = {
        "started_tied": set(map(tuple, live)) == {("p", "p", "out"), ("q", "q", "out")},
        "picked": chosen == "m",
        "asked_env": answer == "w",
        "resolved": after == [("p", "p", "out")],
        "qualified": qualified == "yes",
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "chosen": chosen,
        "answer": answer,
        "failed": failed,
        "claim": "learner picked the question; environment answered; one path remained"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/runtime_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
