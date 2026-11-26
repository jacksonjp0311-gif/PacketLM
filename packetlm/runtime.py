"""Active step.

A tie keeps both candidates.
New evidence kills one.
Distractors and the oracle stay.
Not a general mind.
"""

from __future__ import annotations
import json
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

def run() -> dict:
    objects = ["bearing", "motor", "machine", "gear", "pump", "line"]
    field = []
    for s, r, o in [
        ("bearing", "in", "motor"), ("motor", "in", "machine"),
        ("bearing", "near", "bench"), ("bench", "near", "wall"),
        ("gear", "in", "pump"), ("pump", "in", "line"),
    ]:
        add(field, s, r, o)
    path = discover(field, [("bearing", "part", "machine"), ("gear", "part", "line")], objects)
    add(field, "seal", "in", "valve")
    add(field, "valve", "in", "plant")
    objects += ["seal", "valve", "plant"]
    # tie, then evidence
    tie_field = []
    for s, r, o in [("x", "p", "y"), ("y", "p", "z"), ("x", "q", "y"), ("y", "q", "z"), ("m", "p", "n")]:
        add(tie_field, s, r, o)
    objs = objects + ["x", "y", "z", "m", "n", "w"]
    both = candidates(tie_field, [("x", "out", "z")], objs)
    add(tie_field, "n", "p", "w")
    add(tie_field, "m", "q", "nope")
    after = candidates(tie_field, [("x", "out", "z"), ("m", "out", "w")], objs)
    checks = {
        "chose_in": path == ("in", "in", "part"),
        "oracle": apply_path(field, path, "seal", objects) == "plant",
        "kept_both": set(both) == {("p", "p", "out"), ("q", "q", "out")},
        "evidence_killed_q": after == [("p", "p", "out")],
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {**checks, "after": after, "failed": failed, "claim": "tie kept; new evidence killed q"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/runtime_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
