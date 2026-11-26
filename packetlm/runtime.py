"""Both relations discovered.

The search is not told isa.
An oracle triple is held out of discovery.
Not a general mind.
"""

from __future__ import annotations
import json
from pathlib import Path
from .field import add, ask, save, load

STATE = Path("data/runtime_state.json")

def discover(field, examples, objects):
    rels = sorted({f["r"] for f in field})
    hits = []
    for first in rels:
        for second in rels:
            ok = True
            out_rel = examples[0][1]
            for s, _, expected in examples:
                mid = ask(field, s, first, objects)
                val = ask(field, mid, second, objects) if mid else None
                if val != expected:
                    ok = False
                    break
            if ok:
                hits.append((first, second, out_rel))
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
        ("bearing", "in", "motor"),
        ("motor", "in", "machine"),
        ("gear", "in", "pump"),
        ("pump", "in", "line"),
    ]:
        add(field, s, r, o)
    examples = [("bearing", "part", "machine"), ("gear", "part", "line")]
    path = discover(field, examples, objects)
    # oracle: a pair never used in discovery
    add(field, "seal", "in", "valve")
    add(field, "valve", "in", "plant")
    objects += ["seal", "valve", "plant"]
    got = apply_path(field, path, "seal", objects)
    oracle = "plant"
    save(STATE, field)
    checks = {
        "both_discovered": path == ("in", "in", "part"),
        "oracle": got == oracle,
        "not_told_isa": path is None or path[0] != "isa",
        "reloaded": len(load(STATE)) == len(field),
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {**checks, "path": path, "got": got, "failed": failed, "claim": "both relations discovered; oracle held out"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/runtime_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
