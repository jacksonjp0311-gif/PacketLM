"""G42 qualify.

Several seeds. Several targets.
A gap sits in the live set and survives.
The hidden target is not saved.
Not a general mind.
"""

from __future__ import annotations
import json
import random
from collections import Counter
from pathlib import Path
from .field import add, ask, save, load
from .runtime import discover, apply_path, judge

STATE = Path("data/qualify_state.json")

def build(n, objects):
    field = []
    for i in range(n):
        name, mid = f"r{i}", f"m{i}"
        add(field, "x", name, mid)
        add(field, mid, name, "z")
        objects += [mid]
        bits = max(1, (n - 1).bit_length())
        for bit in range(bits):
            sub, val = f"q{bit}", "yes" if (i >> bit) & 1 else "no"
            hop = f"h{i}_{bit}"
            add(field, sub, name, hop)
            add(field, hop, name, val)
            objects += [sub, hop, val]
    return field

def candidates(field, objects):
    rels = sorted({f["r"] for f in field if f["s"] == "x"})
    return [
        (a, a, "out")
        for a in rels
        if ask(field, ask(field, "x", a, objects) or "", a, objects) == "z"
    ]

def pick(field, paths, objects, skip):
    best, best_score = None, 0
    for s in sorted({f["s"] for f in field if f["s"].startswith("q")}):
        if s in skip:
            continue
        preds = [apply_path(field, p, s, objects) for p in paths]
        known = [p for p in preds if p is not None]
        counts = Counter(known)
        score = min(counts.values()) if len(counts) >= 2 else 0
        if score > best_score:
            best, best_score = s, score
    return best

def investigate(field, paths, objects, query, budget=8):
    asked, live = [], list(paths)
    for _ in range(budget):
        if sum(1 for p in live if p[0] != "gap") <= 1:
            break
        q = pick(field, live, objects, set(asked))
        if not q:
            break
        ans = query(q)
        asked.append(q)
        live = [p for p in live if judge(apply_path(field, p, q, objects), ans) != "contradicted"]
    return live, asked

def run() -> dict:
    o_objects = ["bearing", "motor", "machine", "gear", "pump", "line", "seal", "valve", "plant"]
    o_field = []
    for s, r, o in [
        ("bearing", "in", "motor"), ("motor", "in", "machine"),
        ("gear", "in", "pump"), ("pump", "in", "line"),
        ("seal", "in", "valve"), ("valve", "in", "plant"),
    ]:
        add(o_field, s, r, o)
    o_path = discover(o_field, [("bearing", "part", "machine"), ("gear", "part", "line")], o_objects)
    seeds = [1, 7, 13, 21]
    results = []
    for seed in seeds:
        rng = random.Random(seed)
        n = 8
        target = rng.randrange(n)
        objects = ["x", "z", "out"]
        field = build(n, objects)
        hidden = (f"r{target}", f"r{target}", "out")

        def query(subject, field=field, hidden=hidden, objects=objects):
            return apply_path(field, hidden, subject, objects)

        start = candidates(field, objects) + [("gap", "gap", "out")]
        live, asked = investigate(field, start, objects, query)
        named = [p for p in live if p[0] != "gap"]
        results.append({"seed": seed, "target": target, "asks": len(asked), "ok": named == [hidden] and ("gap", "gap", "out") in live,
                        "gap_live": ("gap", "gap", "out") in live})
    save(STATE, {"results": [{k: v for k, v in r.items() if k != "target"} for r in results]})
    loaded = load(STATE)
    checks = {
        "oracle": apply_path(o_field, o_path, "seal", o_objects) == "plant",
        "all_seeds": all(r["ok"] for r in results),
        "varied": len({r["target"] for r in results}) > 1,
        "gap_in_loop": all(r["gap_live"] for r in results),  # was a truthy tuple and all_seeds (G44 audit item 11)
        "target_not_saved": "target" not in json.dumps(loaded),
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {**checks, "results": results, "failed": failed, "claim": "four seeds; gap stays in the loop; target not saved"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/qualify_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
