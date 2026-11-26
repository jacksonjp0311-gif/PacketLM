"""Generate the question.

Subjects come from the field, not a handed list.
The oracle is back.
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

def subjects_of(field):
    return sorted({f["s"] for f in field})

def pick(field, paths, objects):
    for s in subjects_of(field):
        preds = {apply_path(field, p, s, objects) for p in paths}
        preds.discard(None)
        if len(preds) > 1:
            return s
    return None

def run() -> dict:
    objects = ["bearing", "motor", "machine", "gear", "pump", "line", "seal", "valve", "plant"]
    field = []
    for s, r, o in [
        ("bearing", "in", "motor"), ("motor", "in", "machine"),
        ("bearing", "near", "bench"), ("bench", "near", "wall"),
        ("gear", "in", "pump"), ("pump", "in", "line"),
        ("seal", "in", "valve"), ("valve", "in", "plant"),
    ]:
        add(field, s, r, o)
    path = discover(field, [("bearing", "part", "machine"), ("gear", "part", "line")], objects)
    # generated question on the tie field
    env = []
    for s, r, o in [
        ("x", "p", "y"), ("y", "p", "z"),
        ("x", "q", "a"), ("a", "q", "z"),
        ("m", "p", "n"), ("n", "p", "w"),
        ("m", "q", "b"), ("b", "q", "nope"),
    ]:
        add(env, s, r, o)
    objs = objects + ["x", "y", "z", "a", "m", "n", "w", "b", "nope"]
    live = candidates(env, [("x", "out", "z")], objs)
    chosen = pick(env, live, objs)
    answer = apply_path(env, ("p", "p", "out"), chosen, objs) if chosen else None
    after = candidates(env, [("x", "out", "z"), (chosen, "out", answer)], objs) if chosen else []
    checks = {
        "oracle": apply_path(field, path, "seal", objects) == "plant",
        "generated": chosen == "m" and "m" in subjects_of(env),
        "resolved": after == [("p", "p", "out")],
        "not_handed": chosen in subjects_of(env),
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "chosen": chosen,
        "failed": failed,
        "claim": "question generated from the field; oracle restored"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/runtime_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
