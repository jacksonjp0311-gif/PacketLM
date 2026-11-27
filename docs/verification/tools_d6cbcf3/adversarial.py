"""Verifier's adversarial honest-teacher searches against the G52 guard space (cdb4828).
Modes:
  fullspace  hidden program over EVERY guard pair present in the world (entity-valued pairs too)
             plus a pair absent from the world (is:/not:), small worlds so the full space often fits 8
  depsep     Y (hidden, prefer recursive/size>=4) taught with `complete` on world A; K = cap:Y>rel:r
             taught on a disjoint world B (cap:Y is NOT offered to K: no Y observation in B)
  depwrong   same world; Y taught with ONE example, no complete (often provisional/wrong);
             K = cap:Y>rel:r taught with complete (cap:Y offered at its current version)
  depsame    as b2bb9b8's dep mode (Y with 2 examples + complete, same world)
  depqual    as depsame, engine with --qualified-library
Honest teacher: all facts told, true values / !none / !several, `complete` after every answer.
Wrong qualified = reply without [provisional] whose value differs from the truth (incl. no-value truth)."""
import random, sys, json, tempfile, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from packetlm.engine import Engine
from mybrute import interp, enum, one

def mkworld(rng, tag, small):
    n = rng.randint(3, 6) if small else rng.randint(5, 10)
    ents = [f"{tag}e{i}" for i in range(n)]
    rels = ["ra", "rb"][: rng.randint(1, 2)]
    tri = set()
    if rng.random() < 0.5:
        for i in range(n - 1):
            if rng.random() < 0.8:
                tri.add((ents[i], rels[0], ents[i + 1]))
    for r in rels:
        for x in ents:
            for _ in range(rng.choice([0, 1] if small else [0, 1, 1, 2])):
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

def pairs_of(tri):
    return sorted({(r, o) for _, r, o in tri})

def teach(eng, name, ents, truthset, rng, comp=True, nex=None, investigate=True):
    vals = [e for e in ents if len(truthset(e)) == 1]
    if len(vals) < (nex or 2):
        return False
    for e in rng.sample(vals, nex or rng.randint(2, min(3, len(vals)))):
        eng.turn(f"example {name}: {e} -> {one(truthset(e))}")
        if comp:
            eng.turn(f"complete {e}")
    for _ in range(6 if investigate else 0):
        ver = eng.version(name)
        if ver and ver["status"] == "qualified":
            break
        q = eng.turn(f"investigate {name}")
        if not q.startswith("what is "):
            break
        s = q.split()[2]
        t = truthset(s)
        v = one(t) if len(t) == 1 else ("!none" if not t else "!several")
        eng.turn(f"example {name}: {s} -> {v}")
        if comp:
            eng.turn(f"complete {s}")
    return True

def wrongq(eng, name, es, ts):
    bad = []
    for e in es:
        r = eng.turn(f"what is {e} {name}")
        got = r.split()[2] if r.startswith(f"{e} {name} ") else None
        t = ts(e)
        tv = one(t) if len(t) == 1 else None
        if got is not None and "[provisional]" not in r and got != tv:
            bad.append((e, got, tv, r))
    return bad

def case(rng, mode):
    small = mode == "fullspace"
    ents, rels, tri = mkworld(rng, "", small)
    fd, path = tempfile.mkstemp(suffix=".json"); os.close(fd); os.unlink(path)
    eng = Engine(path, programs=True, answers=True, qualified_library=(mode == "depqual"))
    st = [f"rel:{r}" for r in rels]
    allp = tri
    extra_tri = []
    if mode == "depsep":
        entsB, relsB, triB = mkworld(rng, "b", False)
        relsB = rels  # same relation names
        extra_tri = triB
    for s, r, o in tri + extra_tri:
        eng.turn(f"fact {s} {r} {o}")
    full = tri + extra_tri
    ref = ref_of(full)
    caps = {}
    if mode == "fullspace":
        ps = pairs_of(tri) + [("absent", "zz")]
        gd = [f"is:{q}:{t}" for q, t in ps] + [f"not:{q}:{t}" for q, t in ps]
        if len(gd) > 14:
            gd = rng.sample(gd, 14)
        pool = [p for k, p in enum(st, gd) if k <= 4]
        hidden = rng.choice(pool)
        ts = lambda e: interp(ref, caps, hidden, e)
        if not teach(eng, "kk", ents, ts, rng):
            return None
        H = hidden
    else:
        gd = ["is:k:ca", "not:k:ca", "is:k:cb"]
        pool = [p for k, p in enum(st, gd) if k <= 4]
        rec = [p for p in pool if p[-1][-1] == "self" or sum(map(len, p)) >= 4]
        hy = rng.choice(rec if rng.random() < 0.7 else pool)
        tY = lambda e: interp(ref, {}, hy, e)
        if mode in ("depwrong", "depprefix"):
            ok = teach(eng, "yy", ents, tY, rng, comp=False, nex=1, investigate=False)
        else:
            ok = teach(eng, "yy", ents, tY, rng, comp=True, nex=2, investigate=(mode != "depsame"))
        if not ok:
            return None
        caps = {"cap:Y": hy}
        H = (("cap:Y", f"rel:{rng.choice(rels)}"),) if mode != "depprefix" else \
            ((f"rel:{rng.choice(rels)}", "cap:Y", f"rel:{rng.choice(rels)}"),)
        ts = lambda e: interp(ref, caps, H, e)
        kents = entsB if mode == "depsep" else ents
        if not teach(eng, "kk", kents, ts, rng):
            return None
    ver = eng.version("kk")
    status = ver["status"] if ver else "none"
    qents = entsB if mode == "depsep" else ents
    bad_dom = wrongq(eng, "kk", qents, ts)
    e2, _, tri2 = mkworld(rng, "n", False)
    for s_, r_, o_ in tri2:
        eng.turn(f"fact {s_} {r_} {o_}")
    ref2 = ref_of(full + tri2)
    bad_new = wrongq(eng, "kk", e2, lambda e: interp(ref2, caps, H, e))
    hyp = eng.state["hypotheses"].get("kk", {})
    return {"mode": mode, "status": status, "hidden": str(H), "Y": str(caps.get("cap:Y")),
            "Ystatus": (eng.version("yy") or {}).get("status"), "seq": ver["seq"] if ver else None,
            "gap": hyp.get("scan", {}).get("guard_gap"), "n_bad_dom": len(bad_dom), "bad_dom": bad_dom[:3],
            "n_bad_new": len(bad_new), "bad_new": bad_new[:2],
            "uses_cap": bool(ver) and any("cap:" in s for s in ver["seq"])}

if __name__ == "__main__":
    N, seed, mode = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    rng = random.Random(seed)
    rows = [r for r in (case(rng, mode) for _ in range(N)) if r]
    q = [r for r in rows if r["status"] == "qualified"]
    print(json.dumps({"mode": mode, "seed": seed, "cases": len(rows), "qualified": len(q),
                      "qualified_gap0": sum(r["gap"] == 0 for r in q),
                      "qualified_using_cap": sum(r["uses_cap"] for r in q),
                      "qualified_with_Y_not_qualified": sum(r["Ystatus"] != "qualified" for r in q),
                      "cases_wrong_qualified_domain": sum(r["n_bad_dom"] > 0 for r in rows),
                      "wrong_qualified_domain_answers": sum(r["n_bad_dom"] for r in rows),
                      "cases_wrong_qualified_new_world": sum(r["n_bad_new"] > 0 for r in rows)}))
    for r in [r for r in rows if r["n_bad_dom"] or r["n_bad_new"]][:6]:
        print(json.dumps(r))
