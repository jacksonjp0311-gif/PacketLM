"""Independent brute force for programs.Exact (verifier's own code: own enumerator from the
grammar docstring, own interpreter, own judgments, own blocker rule). Only Exact/Inducer/Ctx
are imported from packetlm, as the system under test."""
import random, sys, json, time
sys.path.insert(0, "/workspace/pl-verify")
from packetlm import programs as P
from itertools import product

MAXD, MAXS = 8, 5

def interp(ref, caps, prog, x, d=0, memo=None):
    if memo is None:
        memo = {}
    if (x, d) in memo:
        return memo[(x, d)]
    r = _interp(ref, caps, prog, x, d, memo)
    memo[(x, d)] = r
    return r

def _interp(ref, caps, prog, x, d, memo):
    for clause in prog:
        cur = {x}
        for t in clause:
            if t == "self":
                cur = set().union(*[interp(ref, caps, prog, y, d + 1, memo) for y in cur]) if d < MAXD else set()
            elif t.startswith("rel:"):
                cur = {z for y in cur for z in ref.get(t[4:], {}).get(y, ())}
            elif t.startswith("is:") or t.startswith("not:"):
                pol, q, v = t.split(":")
                cur = {y for y in cur if (v in ref.get(q, {}).get(y, ())) == (pol == "is")}
            else:
                cur = {z for y in cur for z in interp(ref, caps, caps[t], y)}
            if not cur:
                break
        if cur:
            return frozenset(cur)
    return frozenset()

def enum(st, gd):
    T = st + gd
    isst = lambda c: any(t in st for t in c)
    isgd = lambda c: any(t in gd for t in c)
    for k in range(1, MAXS + 1):
        if k <= 3:
            for c in product(T, repeat=k):
                if isst(c):
                    yield k, (c,)
        for a in range(1, 4):
            b = k - a
            if not 1 <= b <= 3:
                continue
            for c1 in product(T, repeat=a):
                if not isgd(c1):
                    continue
                for c2 in product(T, repeat=b):
                    if isst(c2):
                        yield k, (c1, c2)
                if b >= 2:
                    for c2 in product(T, repeat=b - 1):
                        yield k, (c1, c2 + ("self",))

def one(s):
    return next(iter(s)) if len(s) == 1 else None

def jopen(out, v):
    if v == "!none":
        return "s" if not out else "c"
    if v == "!several":
        return "s" if len(out) >= 2 else ("c" if len(out) == 1 else "u")
    o = one(out)
    return "u" if o is None else ("s" if o == v else "c")

def jclosed(out, v):
    if v == "!none":
        return "s" if not out else "c"
    if v == "!several":
        return "s" if len(out) >= 2 else "c"
    return "s" if out == {v} else "c"

def world(rng):
    kind = rng.random()
    n = rng.randint(4, 9)
    ents = [f"e{i}" for i in range(n)]
    rels = [f"r{i}" for i in range(rng.randint(1, 3 if kind < 0.3 else 2))]
    ref = {}
    if kind < 0.25:  # long chain (> MAX_DEPTH) plus side edges: exercises the depth cap
        n = rng.randint(10, 13); ents = [f"e{i}" for i in range(n)]
        for i in range(n - 1):
            ref.setdefault(rels[0], {}).setdefault(ents[i], set()).add(ents[i + 1])
        if rng.random() < 0.5:
            ref[rels[0]].setdefault(ents[-1], set()).add(ents[rng.randrange(n)])  # cycle back
    for r in rels:
        for x in ents:
            for _ in range(rng.choice([0, 0, 1, 1, 2])):
                ref.setdefault(r, {}).setdefault(x, set()).add(rng.choice(ents))
    for x in ents:
        if rng.random() < 0.7:
            ref.setdefault("k", {}).setdefault(x, set()).add(rng.choice(["ca", "cb", "cc"]))
    caps = {}
    if rng.random() < 0.6:
        cp = tuple(rng.choice([f"rel:{r}" for r in rels] + ["is:k:ca", "not:k:cb"]) for _ in range(rng.randint(1, 2)))
        if not any(t.startswith("rel:") for t in cp):
            cp = cp + (f"rel:{rels[0]}",)
        caps["cap:c@1"] = (cp,)
    st = [f"rel:{r}" for r in rels] + list(caps)
    gpairs = [("k", "ca"), ("k", "cb"), ("k", "cc")][: rng.randint(1, 2 if len(st) > 2 else 3)]
    gd = [f"is:{q}:{t}" for q, t in gpairs] + [f"not:{q}:{t}" for q, t in gpairs]
    allp = [p for _, p in enum(st, gd) if sum(map(len, p)) <= rng.randint(2, 5)]
    hidden = rng.choice(allp)
    dom = sorted(rng.sample(ents, rng.randint(max(2, n // 2), n)), key=lambda e: int(e[1:]))
    obs = []
    for s in rng.sample(ents, rng.randint(1, min(4, n))):
        out = interp(ref, caps, hidden, s)
        if len(out) == 1:
            obs.append((s, one(out)))
        elif rng.random() < 0.6:
            obs.append((s, "!none" if not out else "!several"))
    if obs and rng.random() < 0.15:
        obs[0] = (obs[0][0], rng.choice(ents + ["!none", "!several"]))
    closed = {s for s, _ in obs if rng.random() < 0.5}
    return ref, caps, st, gpairs, gd, dom, obs, closed

def check(rng):
    ref, caps, st, gpairs, gd, dom, obs, closed = world(rng)
    rels = [t[4:] for t in st if t.startswith("rel:")]
    capfn = (lambda tok, y: interp(ref, caps, caps[tok], y)) if caps else None
    ctx = P.Ctx(ref, capfn)
    dom_full = sorted(set(dom) | {s for s, _ in obs})
    ind = P.Inducer(ctx, obs, dom, (rels, list(caps)), gpairs, closed=closed)
    # candidate: my own smallest all-supported program (first in order), else first program
    progs = list(enum(st, gd))
    J = lambda s, out, v: (jclosed if s in closed else jopen)(out, v)
    cand = None
    for k in range(1, MAXS + 1):
        sup = [p for kk, p in progs if kk == k and all(J(s, interp(ref, caps, p, s), v) == "s" for s, v in obs)]
        if sup:
            cand = sup[0]; break
    if cand is None:
        cand = progs[0][1]
    cpred = {e: interp(ref, caps, cand, e) for e in dom}
    seen, order = {}, []
    t0 = time.process_time()
    for _, p in progs:
        if p == cand:
            continue
        outs = {e: interp(ref, caps, p, e) for e in dom_full}
        beh = tuple(outs[e] for e in dom_full)
        if beh in seen:
            continue
        m = [J(s, outs[s], v) for s, v in obs]
        blk = False
        if "c" not in m:
            diffs = [(one(outs[e]), one(cpred[e])) for e in dom]
            differs = any(a != b for a, b in diffs)
            conflict = any(a != b and a is not None and b is not None for a, b in diffs)
            blk = conflict or (m.count("s") >= 1 and differs)
        seen[beh] = blk
        if blk:
            order.append(P.fmt(p))
    tb = time.process_time() - t0
    t0 = time.process_time()
    ex = P.Exact(ind).run(cand, cpred, keep=10 ** 9)
    te = time.process_time() - t0
    ok = ex["complete"] and ex["programs"] == len(progs) and ex["blockers"] == order and ex["blocking_behaviours"] == len(order)
    return ok, {"programs": len(progs), "exact_programs": ex["programs"], "blockers": len(order),
                "exact_blockers": len(ex["blockers"]), "qualified": not order, "closed": len(closed),
                "px": sum(v.startswith("!") for _, v in obs), "brute_s": round(tb, 2), "exact_s": round(te, 3),
                "diff": None if ok else {"mine": order[:4], "exact": ex["blockers"][:4]}}

if __name__ == "__main__":
    N, seed = int(sys.argv[1]), int(sys.argv[2])
    rng = random.Random(seed)
    rows = [check(rng) for _ in range(N)]
    bad = [r for ok, r in rows if not ok]
    rs = [r for _, r in rows]
    print(json.dumps({"cases": N, "seed": seed, "identical": N - len(bad), "qualified": sum(r["qualified"] for r in rs),
                      "with_closed": sum(r["closed"] > 0 for r in rs), "with_px": sum(r["px"] > 0 for r in rs),
                      "max_programs": max(r["programs"] for r in rs),
                      "brute_s": round(sum(r["brute_s"] for r in rs), 1), "exact_s": round(sum(r["exact_s"] for r in rs), 2)}))
    for r in bad[:5]:
        print(json.dumps(r))
