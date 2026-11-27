"""Exactness of programs.Exact against brute force (docs/G49.md).
For random small worlds (relations, class guards, a capability, recursion, PX statements, `complete` subjects) compare
the exact pruned scan with a brute-force enumeration of EVERY program of size <= MAX_SIZE
(no SCAN_BUDGET, no BLOCK_KEEP):
  - total number of programs covered (exact counts multiplicities) == brute-force count + 1 (cand),
  - the list of canonical-first programs of the blocking behaviours, in enumeration order, identical,
  - number of blocking behaviours identical, and therefore the qualified/provisional decision.
Run: python3 -m packetlm.scan_exact_proof [--cases N] [--seed S] [--out PATH]
"""
from __future__ import annotations
import json
import random
import sys
import time
from pathlib import Path

from . import programs as P


def world(rng):
    n = rng.randint(4, 8)
    ents = [f"e{i}" for i in range(n)]
    rels = [f"r{i}" for i in range(rng.randint(1, 2))]
    ref = {}
    for r in rels:
        for x in ents:
            for _ in range(rng.choice([0, 1, 1, 2])):
                ref.setdefault(r, {}).setdefault(x, set()).add(rng.choice(ents))
    for x in ents:
        if rng.random() < 0.7:
            ref.setdefault("k", {}).setdefault(x, set()).add(rng.choice(["ca", "cb"]))
    capprog = ((f"rel:{rng.choice(rels)}",),)
    use_cap = rng.random() < 0.5
    cap = (lambda tok, y: P.run(P.Ctx(ref), capprog, y)) if use_cap else None
    ctx = P.Ctx(ref, cap)
    steps = (rels, ["cap:c@1"] if use_cap else [])
    guards = [("k", "ca"), ("k", "cb")][: rng.randint(1, 2)]
    # observations from a random hidden program (sometimes noisy, sometimes PX statements)
    ind0 = P.Inducer(ctx, [], ents, steps, guards)
    k = rng.randint(1, 4)
    pool = list(ind0.programs(k))
    hidden = rng.choice(pool)
    obs = []
    for s in rng.sample(ents, rng.randint(1, min(4, n))):
        out = P.run(ctx, hidden, s)
        if len(out) == 1:
            obs.append((s, next(iter(out))))
        elif rng.random() < 0.6:
            obs.append((s, "!none" if not out else "!several"))
    if rng.random() < 0.15 and obs:
        obs[0] = (obs[0][0], rng.choice(ents))  # noisy teacher
    # G49: some observed subjects stated `complete` (closed-world judgment there)
    closed = {o[0] for o in obs if rng.random() < 0.4}
    return ctx, obs, ents, steps, guards, closed


def brute(ind, cand, cand_pred):
    seen, order, count = {}, [], 0
    for k in range(1, P.MAX_SIZE + 1):
        for p in ind.programs(k):
            count += 1
            if p == cand:
                continue
            beh = tuple(P.run(ind.ctx, p, e) for e in sorted(set(ind.domain) | {s for s, _ in ind.obs}))
            if beh in seen:
                continue
            m = ind.marks(p)
            block = False
            if "contradicted" not in m:
                support = m.count("supported")
                differs = conflict = False
                for e in ind.domain:
                    a, b = P.one(P.run(ind.ctx, p, e)), P.one(cand_pred[e])
                    if a != b:
                        differs = True
                        if a is not None and b is not None:
                            conflict = True
                            break
                block = conflict or (support >= 1 and differs)
            seen[beh] = block
            if block:
                order.append(P.fmt(p))
    return order, count


def main(argv):
    cases = int(argv[argv.index("--cases") + 1]) if "--cases" in argv else 60
    seed = int(argv[argv.index("--seed") + 1]) if "--seed" in argv else 4901
    rng = random.Random(seed)
    rows, ok_all = [], True
    for c in range(cases):
        ctx, obs, ents, steps, guards, closed = world(rng)
        ind = P.Inducer(ctx, obs, ents, steps, guards, closed=closed)
        k, sup = ind.search()
        cand = sup[0] if sup else next(ind.programs(1))
        cand_pred = {e: P.run(ctx, cand, e) for e in ind.domain}
        t0 = time.process_time()
        order, count = brute(ind, cand, cand_pred)
        tb = time.process_time() - t0
        t0 = time.process_time()
        ex = P.Exact(ind).run(cand, cand_pred, keep=10 ** 9)
        te = time.process_time() - t0
        same = (ex["blockers"] == order and ex["programs"] == count and ex["complete"]
                and ex["blocking_behaviours"] == len(order))
        ok_all &= same
        rows.append({"case": c, "obs": len(obs), "px": sum(v.startswith("!") for _, v in obs), "closed": len(closed),
                     "tokens": len(steps[0]) + len(steps[1]) + 2 * len(guards), "programs": count,
                     "blocking_behaviours": len(order), "qualified_brute": not order,
                     "qualified_exact": not ex["blockers"], "identical": same,
                     "brute_s": round(tb, 3), "exact_s": round(te, 3)})
        if not same:
            rows[-1]["diff"] = {"brute": order[:5], "exact": ex["blockers"][:5], "count": [count, ex["programs"]]}
    rep = {"cases": cases, "seed": seed, "all_identical": ok_all,
           "qualified_cases": sum(r["qualified_brute"] for r in rows),
           "with_px": sum(r["px"] > 0 for r in rows), "with_closed": sum(r["closed"] > 0 for r in rows), "rows": rows}
    if "--out" in argv:
        Path(argv[argv.index("--out") + 1]).write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k != "rows"}))
    bad = [r for r in rows if not r["identical"]]
    if bad:
        print(json.dumps(bad[:3], indent=1))
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
