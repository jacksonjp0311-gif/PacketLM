"""Discrimination.

Several relations exist. Only one pair fits both examples.
Two pairs that both fit must abstain.
Oracle is held out.
Not a general mind.
"""

from __future__ import annotations
import json
from pathlib import Path
from .field import add, ask, save, load

STATE = Path("data/runtime_state.json")

def discover(field, examples, objects):
    rels = sorted({f["r"] for f in field})
    out_rels = {out for _, out, _ in examples}
    if len(out_rels) != 1:
        return None
    out_rel = next(iter(out_rels))
    hits = []
    for first in rels:
        for second in rels:
            if all(
                ask(field, ask(field, s, first, objects) or "", second, objects) == expected
                for s, _, expected in examples
            ):
                hits.append((first, second, out_rel))
    return hits[0] if len(hits) == 1 else None

def apply_path(field, path, subject, objects):
    if not path:
        return None
    first, second, _ = path
    mid = ask(field, subject, first, objects)
    return ask(field, mid, second, objects) if mid else None

def run() -> dict:
    objects = ["bearing", "motor", "machine", "gear", "pump", "line", "a", "b", "c"]
    field = []
    for s, r, o in [
        ("bearing", "in", "motor"),
        ("motor", "in", "machine"),
        ("bearing", "near", "bench"),
        ("bench", "near", "wall"),
        ("gear", "in", "pump"),
        ("pump", "in", "line"),
        ("gear", "beside", "bin"),
    ]:
        add(field, s, r, o)
    path = discover(field, [("bearing", "part", "machine"), ("gear", "part", "line")], objects)
    add(field, "seal", "in", "valve")
    add(field, "valve", "in", "plant")
    objects += ["seal", "valve", "plant"]
    # tie: two relations that both explain the same examples
    tie_field = []
    for s, r, o in [("x", "p", "y"), ("y", "p", "z"), ("x", "q", "y"), ("y", "q", "z")]:
        add(tie_field, s, r, o)
    tie = discover(tie_field, [("x", "out", "z")], objects + ["x", "y", "z"])
    checks = {
        "chose_in": path == ("in", "in", "part"),
        "oracle": apply_path(field, path, "seal", objects) == "plant",
        "tie_abstain": tie is None,
        "more_than_one_rel": len({f["r"] for f in field}) >= 3,
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {**checks, "path": path, "failed": failed, "claim": "distractors rejected; a tie abstains"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/runtime_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
