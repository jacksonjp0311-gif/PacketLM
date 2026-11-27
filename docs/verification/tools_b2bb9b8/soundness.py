"""Engine-level soundness search for `complete X` with an HONEST teacher (verifier's harness).
Random small worlds; hidden program from the G48 grammar; all facts told; value examples +
`complete s` for every answered subject; investigate answered truthfully (values, !none/!several,
+ complete). Then every entity is queried. Count qualified answers that are wrong (domain), and,
after a fresh disconnected world is told, qualified answers that are wrong there."""
OPEN = False
import random, sys, json, tempfile, os
sys.path.insert(0, "/workspace/pl-verify"); sys.path.insert(0, __import__("os").path.dirname(__file__))
from packetlm.engine import Engine
from mybrute import interp, enum, one

def mkworld(rng, tag=""):
    n = rng.randint(5, 10)
    ents = [f"{tag}e{i}" for i in range(n)]
    rels = ["ra", "rb"][: rng.randint(1, 2)]
    tri = set()
    if rng.random() < 0.5:  # chain for recursion
        for i in range(n - 1):
            if rng.random() < 0.8:
                tri.add((ents[i], rels[0], ents[i + 1]))
    for r in rels:
        for x in ents:
            for _ in range(rng.choice([0, 1, 1, 2])):
                tri.add((x, r, rng.choice(ents)))
    for x in ents:
        if rng.random() < 0.6:
            tri.add((x, "k", rng.choice(["ca", "cb"])))
    return ents, rels, sorted(tri)

def ref_of(tri):
    ref = {}
    for s, r, o in tri:
        ref.setdefault(r, {}).setdefault(s, set()).add(o)
    return ref

def case(rng, mode):
    global OPEN
    ents, rels, tri = mkworld(rng)
    st = [f"rel:{r}" for r in rels]
    gd = ["is:k:ca", "not:k:ca", "is:k:cb"]
    pool = [p for k, p in enum(st, gd) if k <= 4]
    hidden = rng.choice(pool)
    caps = {}
    fd, path = tempfile.mkstemp(suffix=".json"); os.close(fd); os.unlink(path)
    eng = Engine(path, programs=True, answers=True)
    LOG = []
    _t = eng.turn
    def turn(l):
        r = _t(l); LOG.append((l, r)); return r
    eng.turn = turn
    for s, r, o in tri:
        eng.turn(f"fact {s} {r} {o}")
    ref = ref_of(tri)
    truthset = lambda e, R=ref: interp(R, caps, hidden, e)
    name = "kk"
    hid2 = None
    if mode == "dep":  # teach Y = hidden first (2 examples), then K = cap:Y>rel:r
        vals = [e for e in ents if len(truthset(e)) == 1]
        if len(vals) < 2:
            return None
        for e in rng.sample(vals, 2):
            eng.turn(f"example yy: {e} -> {one(truthset(e))}")
            (OPEN or eng.turn(f"complete {e}"))
        caps = {"cap:Y": hidden}
        hid2 = (("cap:Y", f"rel:{rng.choice(rels)}"),)
        truthset = lambda e, R=ref: interp(R, caps, hid2, e)
    vals = [e for e in ents if len(truthset(e)) == 1]
    if len(vals) < 2:
        return None
    exs = rng.sample(vals, rng.randint(2, min(3, len(vals))))
    for e in exs:
        eng.turn(f"example {name}: {e} -> {one(truthset(e))}")
        (OPEN or eng.turn(f"complete {e}"))
    for _ in range(6):
        cap = eng.state["capabilities"].get(name)
        ver = cap["versions"][cap["current"] - 1] if cap and cap.get("current") else None
        if ver and ver["status"] == "qualified":
            break
        q = eng.turn(f"investigate {name}")
        if not q.startswith("what is "):
            break
        s = q.split()[2]
        t = truthset(s)
        v = one(t) if len(t) == 1 else ("!none" if not t else "!several")
        eng.turn(f"example {name}: {s} -> {v}")
        (OPEN or eng.turn(f"complete {s}"))
    cap = eng.state["capabilities"].get(name)
    ver = cap["versions"][cap["current"] - 1] if cap and cap.get("current") else None
    status = ver["status"] if ver else "none"
    def wrongq(es, ts):
        bad = []
        for e in es:
            r = eng.turn(f"what is {e} {name}")
            got = r.split()[2] if r.startswith(f"{e} {name} ") else None
            prov = "[provisional]" in r
            t = ts(e)
            tv = one(t) if len(t) == 1 else None
            if got is not None and not prov and got != tv:
                bad.append((e, got, tv, r))
        return bad
    bad_dom = wrongq(ents, truthset)
    obs_s = {o[0] for o in eng.state["observations"].get(name, [])}
    adj = {}
    for a_, _, b_ in tri:
        adj.setdefault(a_, set()).add(b_); adj.setdefault(b_, set()).add(a_)
    comp, todo = set(obs_s), list(obs_s)
    while todo:
        for z in adj.get(todo.pop(), ()):
            if z not in comp:
                comp.add(z); todo.append(z)
    gs = {tuple(g) for g in eng.state["hypotheses"].get(name, {}).get("guards", [])}
    htoks = [t for c in (hid2 if mode == "dep" else hidden) for t in c if t.startswith(("is:", "not:"))]
    in_space = all(tuple(t.split(":")[1:]) in gs for t in htoks)
    bad_in = [b for b in bad_dom if b[0] in comp]
    e2, _, tri2 = mkworld(rng, tag="n")
    for s_, r_, o_ in tri2:
        eng.turn(f"fact {s_} {r_} {o_}")
    ref2 = ref_of(tri + tri2)
    H = hid2 if mode == "dep" else hidden
    bad_new = wrongq(e2, lambda e: interp(ref2, caps, H, e))
    return {"mode": mode, "status": status, "hidden": str(H), "seq": ver["seq"] if ver else None,
            "n_bad_dom": len(bad_dom), "n_bad_in_domain": len(bad_in), "hidden_in_space": in_space, "bad_dom": bad_dom[:3], "n_bad_new": len(bad_new), "bad_new": bad_new[:2],
            "completes": len(eng.state.get("complete", {})), "tri": tri if bad_dom else None,
            "log": [x for x in LOG if not x[0].startswith("fact ")][:40] if bad_dom else None,
            "hyp": {k: v for k, v in eng.state["hypotheses"].get(name, {}).items() if k in ("scan", "supported_programs", "guards")} if bad_dom else None}

if __name__ == "__main__":
    N, seed, mode = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    OPEN = len(sys.argv) > 4 and sys.argv[4] == "open"
    rng = random.Random(seed)
    rows = [r for r in (case(rng, mode) for _ in range(N)) if r]
    q = [r for r in rows if r["status"] == "qualified"]
    print(json.dumps({"mode": mode, "seed": seed, "cases": len(rows), "qualified": len(q),
                      "cases_wrong_qualified_domain": sum(r["n_bad_dom"] > 0 for r in rows),
                      "wrong_qualified_domain_answers": sum(r["n_bad_dom"] for r in rows),
                      "cases_wrong_qualified_new_entities": sum(r["n_bad_new"] > 0 for r in rows)}))
    print(json.dumps({"bad_cases": sum(r["n_bad_dom"] > 0 for r in rows),
        "bad_in_domain_cases": sum(r["n_bad_in_domain"] > 0 for r in rows),
        "bad_in_domain_hidden_in_space": sum(r["n_bad_in_domain"] > 0 and r["hidden_in_space"] for r in rows),
        "bad_in_domain_hidden_outside_space": sum(r["n_bad_in_domain"] > 0 and not r["hidden_in_space"] for r in rows),
        "bad_only_outside_domain": sum(r["n_bad_dom"] > 0 and r["n_bad_in_domain"] == 0 for r in rows),
        "qualified_hidden_in_space": sum(r["status"] == "qualified" and r["hidden_in_space"] for r in rows)}))
    for r in [r for r in rows if r["n_bad_in_domain"] and r["hidden_in_space"]][:3]:
        print(json.dumps(r))
    for r in [r for r in rows if r["n_bad_dom"]][:0]:
        print(json.dumps(r))
