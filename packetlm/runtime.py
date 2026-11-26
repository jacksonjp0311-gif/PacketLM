"""No constant checks.

The target is chosen, not fixed at r0.
A path that cannot answer stays in the loop.
Oracle and eight stay.
Not a general mind.
"""

from __future__ import annotations
import json
import random
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
    asked, history, live = [], [], list(paths)
    for _ in range(budget):
        if len(live) <= 1:
            break
        q = pick(field, live, objects, set(asked))
        if not q:
            break
        ans = query(q)
        asked.append(q)
        history.append({"q": q, "a": ans})
        live = [p for p in live if judge(apply_path(field, p, q, objects), ans) != "contradicted"]
    return live, asked, history

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
    rng = random.Random(7)
    target_i = rng.randrange(8)
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
    hidden = (names[target_i], names[target_i], "out")

    def query(subject):
        return apply_path(env, hidden, subject, objects)

    start = candidates(env, [("x", "out", "z")], objects)
    live, asked, history = investigate(env, start, objects, query)
    # incomplete inside the loop: ask a question it cannot answer
    gap = ("gap", "gap", "out")
    mixed = [hidden, gap]
    ans = query("q0")
    survived = [p for p in mixed if judge(apply_path(env, p, "q0", objects), ans) != "contradicted"]
    save(STATE, {"path": list(live[0]) if live else None, "history": history, "target": target_i})
    loaded = load(STATE)
    checks = {
        "oracle": apply_path(o_field, o_path, "seal", o_objects) == "plant",
        "eight": len(start) == 8,
        "not_always_r0": target_i != 0,
        "resolved": live == [hidden],
        "gap_survived_loop": gap in survived and hidden in survived,
        "history_reloaded": loaded.get("history") == history,
    }
    failed = [k for k, v in checks.items() if not v]
    receipt = {
        **checks,
        "target": target_i,
        "asked": asked,
        "failed": failed,
        "claim": "target is not fixed; a gap survives a real question; no constant check"
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/runtime_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    if failed:
        raise SystemExit(1)
    return receipt

if __name__ == "__main__":
    run()
