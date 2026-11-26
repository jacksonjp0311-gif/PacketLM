"""Ask the scored question.

The even split is chosen, asked, and used.
Oracle stays.
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

def split_score(preds):
    counts = Counter(p for p in preds if p is not None)
    return min(counts.values()) if len(counts) >= 2 else 0

def pick(field, paths, objects):
    best, best_score = None, 0
    for s in sorted({f["s"] for f in field}):
        score = split_score([apply_path(field, p, s, objects) for p in paths])
        if score > best_score:
            best, best_score = s, score
    return best, best_score

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
    ]:
        add(env, s, r, o)
    objs = objects + ["x", "y", "z", "a", "c", "m", "n", "w", "b", "d", "nope"]
    live = candidates(env, [("x", "out", "z")], objs)
    chosen, score = pick(env, live, objs)
    answer = apply_path(env, ("p", "p", "out"), chosen, objs) if chosen else None
    after = candidates(env, [("x", "out", "z"), (chosen, "out", answer)], objs) if chosen else []
    save(STATE, {"path": after, "chosen": chosen})
    checks = {
        "oracle": apply_path(field, path, "seal", objects) == "plant",
        "picked_even": chosen == "m",
        "resolved": after == [("p", "p", "out")],
        "reloaded": load(STATE).get("path") == after,
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {**checks, "chosen": chosen, "score": score, "failed": failed, "claim": "scored question asked; one path remained"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/runtime_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
