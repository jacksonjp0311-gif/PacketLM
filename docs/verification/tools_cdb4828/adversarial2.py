"""Verifier's second adversarial set (cdb4828): stale qualification after the domain grows.
  grow     K (hidden over the full guard space, small world) taught with `complete` until qualified;
           then new told facts with subjects at UNOBSERVED domain nodes (no closure touched) plus new
           entities hanging off them; truth recomputed on the new facts; every original entity queried.
  depgrow  Y (recursive preferred) taught with complete on world A; then world B attached to A by
           edges B->A; K = cap:Y>rel:r taught with complete on B nodes; all of A and B queried.
Wrong qualified = reply without [provisional] whose value differs from the truth on CURRENT facts."""
import random, sys, json, tempfile, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from packetlm.engine import Engine
from mybrute import interp, enum, one
from adversarial import mkworld, ref_of, pairs_of, teach, wrongq

def case(rng, mode):
    fd, path = tempfile.mkstemp(suffix=".json"); os.close(fd); os.unlink(path)
    eng = Engine(path, programs=True, answers=True)
    if mode == "grow":
        ents, rels, tri = mkworld(rng, "", True)
        for s, r, o in tri:
            eng.turn(f"fact {s} {r} {o}")
        ps = pairs_of(tri) + [("absent", "zz")]
        gd = [f"is:{q}:{t}" for q, t in ps] + [f"not:{q}:{t}" for q, t in ps]
        if len(gd) > 14:
            gd = rng.sample(gd, 14)
        st = [f"rel:{r}" for r in rels]
        H = rng.choice([p for k, p in enum(st, gd) if k <= 4])
        ref = ref_of(tri)
        if not teach(eng, "kk", ents, lambda e: interp(ref, {}, H, e), rng):
            return None
        ver = eng.version("kk")
        if not ver or ver["status"] != "qualified":
            return {"status": ver["status"] if ver else "none", "n_bad": 0}
        observed = {o[0] for o in eng.state["observations"]["kk"]}
        closed = set(eng.state.get("complete", {}))
        inclos = set().union(*[set(v["closure"]) for v in eng.state.get("complete", {}).values()]) if closed else set()
        free = [e for e in ents if e not in inclos]
        if not free:
            return {"status": "qualified", "n_bad": 0, "nofree": True}
        new = []
        for i in range(rng.randint(1, 4)):
            s = rng.choice(free)
            o = rng.choice(ents + [f"g{i}"])
            new.append((s, rng.choice(rels), o))
            if rng.random() < 0.5:
                new.append((f"g{i}", "k", rng.choice(["ca", "cb"])))
        for s, r, o in new:
            eng.turn(f"fact {s} {r} {o}")
        tri2 = sorted(set(tri) | set(new))
        ref2 = ref_of(tri2)
        bad = wrongq(eng, "kk", ents, lambda e: interp(ref2, {}, H, e))
        return {"status": "qualified", "H": str(H), "seq": ver["seq"], "new": new, "n_bad": len(bad), "bad": bad[:3],
                "retracted": len(eng.state.get("complete_log", []))}
    # depgrow
    entsA, rels, triA = mkworld(rng, "a", False)
    for s, r, o in triA:
        eng.turn(f"fact {s} {r} {o}")
    st = [f"rel:{r}" for r in rels]
    gd = ["is:k:ca", "not:k:ca", "is:k:cb"]
    pool = [p for k, p in enum(st, gd) if k <= 4]
    rec = [p for p in pool if p[-1][-1] == "self"]
    hy = rng.choice(rec)
    refA = ref_of(triA)
    if not teach(eng, "yy", entsA, lambda e: interp(refA, {}, hy, e), rng):
        return None
    yv = eng.version("yy")
    entsB, _, triB = mkworld(rng, "b", False)
    triB = [(s, rels[0] if r not in ("k",) and r not in rels else r, o) for s, r, o in triB]
    links = [(rng.choice(entsB), rng.choice(rels), rng.choice(entsA)) for _ in range(rng.randint(1, 3))]
    for s, r, o in triB + links:
        eng.turn(f"fact {s} {r} {o}")
    full = triA + triB + links
    ref = ref_of(full)
    caps = {"cap:Y": hy}
    H = (("cap:Y", f"rel:{rng.choice(rels)}"),)
    ts = lambda e: interp(ref, caps, H, e)
    if not teach(eng, "kk", entsB, ts, rng):
        return None
    ver = eng.version("kk")
    bad = wrongq(eng, "kk", entsA + entsB, ts)
    return {"status": ver["status"] if ver else "none", "Ystatus": yv["status"] if yv else None, "Y": str(hy),
            "seq": ver["seq"] if ver else None, "uses_cap": bool(ver) and any("cap:" in s for s in ver["seq"]),
            "n_bad": len(bad), "bad": bad[:3]}

if __name__ == "__main__":
    N, seed, mode = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    rng = random.Random(seed)
    rows = [r for r in (case(rng, mode) for _ in range(N)) if r]
    q = [r for r in rows if r["status"] == "qualified"]
    print(json.dumps({"mode": mode, "seed": seed, "cases": len(rows), "qualified": len(q),
                      "qualified_using_cap": sum(bool(r.get("uses_cap")) for r in q),
                      "cases_wrong_qualified": sum(r["n_bad"] > 0 for r in rows),
                      "wrong_qualified_answers": sum(r["n_bad"] for r in rows)}))
    for r in [r for r in rows if r["n_bad"]][:5]:
        print(json.dumps(r))
