"""Verifier's third adversarial set (050bebd): stale or wrong qualified answers after fact
additions and removals (S1/L1 of cdb4828), across process boundaries, in all modes.
Modes:
  prog     --programs, hidden over the full guard space of a small world, `complete` after answers
  base     base engine (relation sequences, length<=3), complete with prob. 0.5
  bounded  as base, engine with --bounded
  dep      --programs: Y taught on the world, K = cap:Y>rel:r taught; operations then hit Y's world
After qualification, 1-6 random operations are applied, each followed by a query of every entity
(old and new) against the truth on CURRENT facts:
  add-known    told fact with subject a known entity (closure members included)
  add-newsub   told fact from a brand-new entity into the world (new -> known)
  add-newobj   told fact from a known entity to a brand-new entity, then facts at the new one
  retract      retract a random told fact
  correct      `correct s r o` on a random told fact
With probability 0.5 the engine is saved and re-opened between operations (fresh process).
Wrong qualified = reply without [provisional] whose value differs from the truth (no value included)."""
import random, sys, json, tempfile, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from packetlm.engine import Engine
from mybrute import interp, enum, one
from adversarial import mkworld, ref_of, pairs_of, teach, wrongq

WITNESS = os.environ.get("ADV_WITNESS") == "1"

def find_witness(eng, tri0, tri, ents, rels, maxk=3):
    """An honest hidden program the stale qualified version answers wrongly: H' gives every recorded
    observation's value on the facts at qualification time AND on the current facts, and differs
    from a current qualified reply. Full guard space on the current facts plus one absent pair."""
    obs = eng.state["observations"]["kk"]
    ref0, ref1 = ref_of(sorted(tri0)), ref_of(sorted(tri))
    ps = pairs_of(sorted(tri)) + [("absent", "zz")]
    gd = [f"is:{q}:{t}" for q, t in ps] + [f"not:{q}:{t}" for q, t in ps]
    st = [f"rel:{r}" for r in rels + ["k"]]
    def tv(ref, p, e):
        t = interp(ref, {}, p, e)
        return one(t) if len(t) == 1 else ("!none" if not t else "!several")
    replies = {}
    for e in ents:
        r = eng.turn(f"what is {e} kk")
        if r.startswith(f"{e} kk ") and "[provisional]" not in r:
            replies[e] = r.split()[2]
    for k, p in enum(st, gd):
        if k > maxk:
            break
        if all(tv(ref0, p, s_) == v_ and tv(ref1, p, s_) == v_ for s_, v_ in obs):
            bad = [(e, g, one(interp(ref1, {}, p, e))) for e, g in replies.items() if one(interp(ref1, {}, p, e)) != g]
            if bad:
                return {"H_prime": str(p), "wrong": bad[:3]}
    return None

def in_space(eng, H, mode):
    """Was the hidden program inside the engine's declared hypothesis space when the wrong qualified
    answer was given? base: length <= horizon. programs: every guard of H among the scanned guards,
    no guard gap. Wrong answers outside the space are the documented open-world assumption."""
    hyp = eng.state["hypotheses"].get("kk", {})
    sc = hyp.get("scan", {})
    if mode in ("base", "bounded"):
        ok = len(H[0]) <= (sc.get("horizon") or 0)
        return {"in_space": ok, "horizon": sc.get("horizon"), "len_H": len(H[0])}
    guards = {f"{k}:{q}:{t}" for q, t in hyp.get("guards", []) for k in ("is", "not")}
    hg = {t for cl in H for t in cl if t.startswith(("is:", "not:"))}
    ver = eng.version("kk") or {}
    return {"history": ver.get("history"), "scan_method": sc.get("method"), "evidence": ver.get("evidence"),
            "state_path": str(eng.path),
            "in_space": hg <= guards and not sc.get("guard_gap"), "missing_guards": sorted(hg - guards),
            "guard_gap": sc.get("guard_gap"), "complete_alive": sorted(eng.state.get("complete", {}))}

def case(rng, mode):
    fd, path = tempfile.mkstemp(suffix=".json", dir=os.environ.get("ADV_DIR")); os.close(fd); os.unlink(path)
    keep = mode == "progkeep"
    if keep:
        mode = "prog"
    kw = dict(answers=True, programs=mode in ("prog", "dep"), bounded=mode == "bounded")
    eng = Engine(path, **kw)
    ents, rels, tri = mkworld(rng, "", mode == "prog")
    tri = set(tri)
    for s, r, o in sorted(tri):
        eng.turn(f"fact {s} {r} {o}")
    st = [f"rel:{r}" for r in rels]
    caps = {}
    comp = True
    if mode == "prog":
        ps = pairs_of(sorted(tri)) + [("absent", "zz")]
        gd = [f"is:{q}:{t}" for q, t in ps] + [f"not:{q}:{t}" for q, t in ps]
        if len(gd) > 14:
            gd = rng.sample(gd, 14)
        H = rng.choice([p for k, p in enum(st, gd) if k <= 4])
    elif mode in ("base", "bounded"):
        H = (tuple(rng.choice(st) for _ in range(rng.randint(1, 3))),)
        comp = rng.random() < 0.5
    else:
        gd = ["is:k:ca", "not:k:ca", "is:k:cb"]
        pool = [p for k, p in enum(st, gd) if k <= 4]
        hy = rng.choice(pool)
        if not teach(eng, "yy", ents, lambda e: interp(ref_of(sorted(tri)), {}, hy, e), rng, comp=True, nex=2):
            return None
        caps = {"cap:Y": hy}
        H = (("cap:Y", f"rel:{rng.choice(rels)}"),)
    truth = lambda e, T: interp(ref_of(sorted(T)), caps, H, e)
    if not teach(eng, "kk", ents, lambda e: truth(e, tri), rng, comp=comp):
        return None
    ver = eng.version("kk")
    if not ver or ver["status"] != "qualified":
        return {"status": ver["status"] if ver else "none", "n_bad": 0, "ops": []}
    hz = ver.get("evidence", {}).get("horizon")
    pre = wrongq(eng, "kk", ents, lambda e: truth(e, tri))
    if pre:  # already wrong before any operation: not a growth/removal finding (reported separately)
        return {"status": "qualified", "pre_bad": len(pre), "pre": pre[:2], "H": str(H), "seq": ver["seq"],
                "horizon": hz, "n_bad": 0, "ops": []}
    allents, ops, bad, nnew = list(ents), [], [], 0
    unverified = False
    witness = None
    tri0 = set(tri)
    names = ["kk"] + (["yy"] if mode == "dep" else [])
    for _ in range(rng.randint(1, 6)):
        kind = rng.choice(["add-known", "add-known", "add-newsub", "add-newobj", "retract", "correct"])
        lines, rel = [], rng.choice(rels + (["k"] if rng.random() < 0.3 else []))
        if kind == "add-known":
            t = (rng.choice(allents), rel, rng.choice(allents + ["ca", "cb"]) if rel == "k" else rng.choice(allents))
            if rel == "k":
                t = (t[0], "k", rng.choice(["ca", "cb"]))
            lines.append(("fact", t))
        elif kind == "add-newsub":
            nnew += 1; x = f"n{nnew}"
            lines.append(("fact", (x, rel if rel != "k" else rels[0], rng.choice(allents))))
            allents.append(x)
        elif kind == "add-newobj":
            nnew += 1; x = f"n{nnew}"
            lines.append(("fact", (rng.choice(allents), rels[0], x)))
            for _ in range(rng.randint(0, 2)):
                r2 = rng.choice(rels + ["k"])
                lines.append(("fact", (x, r2, rng.choice(["ca", "cb"]) if r2 == "k" else rng.choice(allents))))
            allents.append(x)
        elif kind in ("retract", "correct") and tri:
            t = rng.choice(sorted(tri))
            if kind == "retract":
                lines.append(("retract", t))
            else:
                o2 = rng.choice(["ca", "cb"]) if t[1] == "k" else rng.choice(allents)
                lines.append(("correct", (t[0], t[1], o2)))
        if keep:
            T2 = set(tri)
            for k, (s, r, o) in lines:
                if k == "fact": T2.add((s, r, o))
                elif k == "retract": T2.discard((s, r, o))
                else: T2 = {x for x in T2 if not (x[0] == s and x[1] == r)} | {(s, r, o)}
            def _tv(e, T):
                t = truth(e, T)
                return one(t) if len(t) == 1 else ("!none" if not t else "!several")
            if any(_tv(s_, T2) != v_ for s_, v_ in eng.state["observations"]["kk"]):
                continue
        for k, (s, r, o) in lines:
            if k == "fact":
                eng.turn(f"fact {s} {r} {o}"); tri.add((s, r, o))
            elif k == "retract":
                eng.turn(f"retract {s} {r} {o}"); tri.discard((s, r, o))
            else:
                eng.turn(f"correct {s} {r} {o}")
                tri = {x for x in tri if not (x[0] == s and x[1] == r)} | {(s, r, o)}
        ops.append([kind, lines])
        if rng.random() < 0.5:
            eng.save(); eng = Engine.open(path, **kw)
        b = wrongq(eng, "kk", allents, lambda e: truth(e, tri))
        _v, _h = eng.version("kk") or {}, eng.state["hypotheses"].get("kk", {})
        if _v.get("status") == "qualified" and _h.get("candidate") is None:
            unverified = True  # last acquisition found no candidate, yet the version stays qualified
            if WITNESS and witness is None:
                witness = find_witness(eng, tri0, tri, allents, rels)
        if mode == "dep":
            b += wrongq(eng, "yy", allents, lambda e: interp(ref_of(sorted(tri)), {}, caps["cap:Y"], e))
        if b:
            bad += [(len(ops), x) for x in b]
            if "diag" not in locals():
                diag = in_space(eng, H, mode)
                # honest-teacher criterion: every recorded observation is still TRUE under H on the
                # current facts (otherwise the world changed the truth at an observed subject, and H is
                # itself contradicted by the teacher's earlier answers)
                def tv(e):
                    t = truth(e, tri)
                    return one(t) if len(t) == 1 else ("!none" if not t else "!several")
                diag["obs_still_true"] = all(tv(s_) == v_ for s_, v_ in eng.state["observations"]["kk"])
    return {"status": "qualified", "H": str(H), "seq": ver["seq"], "ops": ops, "n_bad": len(bad), "bad": bad[:3],
            "final_status": (eng.version("kk") or {}).get("status"), "unverified": unverified, "witness": witness, **({"diag": diag} if bad else {})}

if __name__ == "__main__":
    N, seed, mode = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    rng = random.Random(seed)
    rows = [r for r in (case(rng, mode) for _ in range(N)) if r]
    q = [r for r in rows if r["status"] == "qualified"]
    print(json.dumps({"mode": mode, "seed": seed, "cases": len(rows), "qualified": len(q),
                      "ops": sum(len(r["ops"]) for r in q),
                      "still_qualified_at_end": sum(r.get("final_status") == "qualified" for r in q),
                      "cases_wrong_before_ops": sum(bool(r.get("pre_bad")) for r in rows),
                      "cases_wrong_qualified": sum(r["n_bad"] > 0 for r in rows),
                      "cases_qualified_after_none_reacquire": sum(bool(r.get("unverified")) for r in rows),
                      "cases_honest_witness_found": sum(bool(r.get("witness")) for r in rows),
                      "cases_wrong_qualified_H_in_space": sum(r["n_bad"] > 0 and r["diag"]["in_space"] for r in rows),
                      "cases_wrong_qualified_obs_still_true": sum(r["n_bad"] > 0 and r["diag"]["obs_still_true"] for r in rows),
                      "wrong_qualified_answers": sum(r["n_bad"] for r in rows)}))
    for r in [r for r in rows if r["n_bad"] or r.get("pre_bad") or r.get("witness")][:6]:
        print(json.dumps(r))
