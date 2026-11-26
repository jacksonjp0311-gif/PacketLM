"""Two steps, forced by coverage.

A question counts only if every live path can answer it.
k is invisible while r is alive.
m is asked first. Then k.
Not a general mind.
"""

from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
from .field import add, ask, save, load

STATE = Path("data/runtime_state.json")

def candidates(field, examples, objects):
    rels = sorted({f["r"] for f in field})
    out_rels = {out for _, out, _ in examples}
    if len(out_rels) != 1:
        return []
    out_rel = next(iter(out_rels))
    return [
        (first, second, out_rel)
        for first in rels
        for second in rels
        if all(
            ask(field, ask(field, s, first, objects) or "", second, objects) == expected
            for s, _, expected in examples
        )
    ]

def discover(field, examples, objects):
    hits = candidates(field, examples, objects)
    return hits[0] if len(hits) == 1 else None

def apply_path(field, path, subject, objects):
    if not path:
        return None
    first, second, _ = path
    mid = ask(field, subject, first, objects)
    return ask(field, mid, second, objects) if mid else None

def pick(field, paths, objects, skip):
    best, best_score = None, 0
    for s in sorted({f["s"] for f in field}):
        if s in skip:
            continue
        preds = [apply_path(field, p, s, objects) for p in paths]
        if any(p is None for p in preds):
            continue
        counts = Counter(preds)
        score = min(counts.values()) if len(counts) >= 2 else 0
        if score > best_score:
            best, best_score = s, score
    return best

def investigate(field, paths, objects, truth, budget=3):
    examples, asked, live = [], [], list(paths)
    for _ in range(budget):
        if len(live) <= 1:
            break
        q = pick(field, live, objects, {s for s, _, _ in examples})
        if not q:
            break
        ans = apply_path(field, truth, q, objects)
        examples.append((q, "out", ans))
        asked.append(q)
        live = [p for p in live if apply_path(field, p, q, objects) == ans]
    return live, asked

def run() -> dict:
    objects = ["bearing", "motor", "machine", "gear", "pump", "line", "seal", "valve", "plant"]
    field = []
    for s, r, o in [
        ("bearing", "in", "motor"), ("motor", "in", "machine"),
        ("gear", "in", "pump"), ("pump", "in", "line"),
        ("seal", "in", "valve"), ("valve", "in", "plant"),
    ]:
        add(field, s, r, o)
    path = discover(field, [("bearing", "part", "machine"), ("gear", "part", "line")], objects)
    env = []
    for s, r, o in [
        ("x", "p", "y"), ("y", "p", "z"),
        ("x", "q", "a"), ("a", "q", "z"),
        ("x", "r", "c"), ("c", "r", "z"),
        ("m", "p", "n"), ("n", "p", "w"),
        ("m", "q", "b"), ("b", "q", "w"),
        ("m", "r", "d"), ("d", "r", "nope"),
        ("k", "p", "e"), ("e", "p", "yes"),
        ("k", "q", "f"), ("f", "q", "no"),
    ]:
        add(env, s, r, o)
    objs = objects + ["x", "y", "z", "a", "c", "m", "n", "w", "b", "d", "nope", "k", "e", "f", "yes", "no"]
    start = candidates(env, [("x", "out", "z")], objs)
    live, asked = investigate(env, start, objs, ("p", "p", "out"))
    stuck_field = []
    for s, r, o in [("x", "p", "y"), ("y", "p", "z"), ("x", "q", "a"), ("a", "q", "z")]:
        add(stuck_field, s, r, o)
    stuck = candidates(stuck_field, [("x", "out", "z")], objs)
    stuck_live, stuck_asked = investigate(stuck_field, stuck, objs, ("p", "p", "out"))
    save(STATE, [{"path": list(p)} for p in live])
    checks = {
        "oracle": apply_path(field, path, "seal", objects) == "plant",
        "started_three": len(start) == 3,
        "asked_twice": asked == ["m", "k"],
        "resolved": [list(p) for p in live] == [["p", "p", "out"]],
        "stuck_abstain": len(stuck_live) == 2 and stuck_asked == [],
        "reloaded": load(STATE) == [{"path": ["p", "p", "out"]}],
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {**checks, "asked": asked, "failed": failed, "claim": "coverage forces two questions; unresolvable abstains"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/runtime_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
