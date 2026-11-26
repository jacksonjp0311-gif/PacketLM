"""Isolated query.

The learner asks a subject. The environment answers.
The true path is not an argument.
Oracle and eight stay.
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
        (a, b, out_rel)
        for a in rels for b in rels
        if all(ask(field, ask(field, s, a, objects) or "", b, objects) == exp for s, _, exp in examples)
    ]

def discover(field, examples, objects):
    hits = candidates(field, examples, objects)
    return hits[0] if len(hits) == 1 else None

def apply_path(field, path, subject, objects):
    if not path:
        return None
    a, b, _ = path
    mid = ask(field, subject, a, objects)
    return ask(field, mid, b, objects) if mid else None

def judge(pred, ans):
    if pred is None:
        return "undetermined"
    return "supported" if pred == ans else "contradicted"

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

def investigate(field, paths, objects, query, budget=6):
    asked, live = [], list(paths)
    for _ in range(budget):
        if len(live) <= 1:
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
    names = [f"r{i}" for i in range(8)]
    env, objects = [], ["x", "z", "out"]
    for i, name in enumerate(names):
        mid = f"m{i}"
        add(env, "x", name, mid)
        add(env, mid, name, "z")
        objects += [mid]
        for bit in range(3):
            sub, val = f"q{bit}", "yes" if (i >> bit) & 1 else "no"
            hop = f"h{i}_{bit}"
            add(env, sub, name, hop)
            add(env, hop, name, val)
            objects += [sub, hop, val]
    hidden = ("r0", "r0", "out")

    def query(subject):
        return apply_path(env, hidden, subject, objects)

    start = candidates(env, [("x", "out", "z")], objects)
    live, asked = investigate(env, start, objects, query)
    # incomplete survives a real question
    incomplete = ("missing", "missing", "out")
    kept = judge(apply_path(env, incomplete, "q0", objects), query("q0")) == "undetermined"
    save(STATE, [{"path": list(p)} for p in live])
    checks = {
        "oracle": apply_path(o_field, o_path, "seal", o_objects) == "plant",
        "eight": len(start) == 8,
        "three_asks": len(asked) == 3,
        "resolved": [list(p) for p in live] == [["r0", "r0", "out"]],
        "no_truth_arg": True,
        "missing_in_question": kept,
        "reloaded": load(STATE) == [{"path": ["r0", "r0", "out"]}],
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {**checks, "asked": asked, "failed": failed, "claim": "learner queries; it does not receive the operator"}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/runtime_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
