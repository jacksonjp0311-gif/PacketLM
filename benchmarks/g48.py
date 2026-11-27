"""G48: acquiring type-constrained, variable-depth and conditional programs on unfamiliar graphs.
Protocol, designed part and thresholds: docs/G48.md (committed before the registered run).
Run: python3 benchmarks/g48.py [--seeds 481,...] [--dev]
"""

from __future__ import annotations
import json
import random
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from packetlm import programs as P  # noqa: E402
from packetlm.g45_test import Names, Teacher, source_hash  # noqa: E402


def engine_hash():
    """sha256 of the engine modules only (no tests, mutations or suite), verification L4."""
    import hashlib
    h = hashlib.sha256()
    for p in sorted((ROOT / "packetlm").glob("*.py")):
        if not p.name.endswith(("_test.py",)) and p.name not in ("mutations.py", "suite.py"):
            h.update(p.name.encode() + p.read_bytes())
    return h.hexdigest()

OUT = ROOT / "artifacts/g48"
ARMS = {"P": ["--programs"], "X": ["--deepen=3"], "S": ["--programs"],
        "A": ["--programs", "--adaptive-retention"]}
SEEDS = [481, 482, 483, 484, 485, 486, 487]
ABSTAIN = False  # PX: also ask every world entity whose truth has no single value (abstention)
RICH = set()  # arms whose teacher states `!none` / `!several` for non-sealed items (docs/PX.md)
QUESTIONS = 4


def ref_of(triples):
    ref = {}
    for s, r, o in triples:
        ref.setdefault(r, {}).setdefault(s, set()).add(o)
    return ref


def truth(triples, hidden, x, lib):
    """Independent interpreter (programs.run_naive); `lib` maps cap tokens to hidden programs."""
    ref = ref_of(triples)
    cap = lambda tok, y: P.run_naive(ref, P.parse(lib[tok]), y)  # noqa: E731
    out = P.run_naive(ref, P.parse(hidden), x, cap)
    return next(iter(out)) if len(out) == 1 else None


def truth_set(triples, hidden, x, lib):
    ref = ref_of(triples)
    cap = lambda tok, y: P.run_naive(ref, P.parse(lib[tok]), y)  # noqa: E731
    return P.run_naive(ref, P.parse(hidden), x, cap)


def world_until(rng, nm):
    U, K, D, C = nm(), nm(), nm(), nm()
    tgt, top, mid1, mid2, leafc, capc = nm(), nm(), nm(), nm(), nm(), nm()
    tri, info, roots = [], {}, []
    topn = nm()
    tri.append((topn, K, top))
    for _ in range(3):
        root = nm()
        roots.append(root)
        tri += [(root, U, topn), (root, K, tgt), (root, C, nm())]
        tri.append((tri[-1][2], K, capc))
        for depth in (1, 2, 3, 4, 5):
            parent = root
            for d in range(1, depth + 1):
                node = nm()
                tri += [(node, U, parent), (node, K, leafc if d == depth else rng.choice([mid1, mid2]))]
                info[node] = {"depth": d, "root": root}
                parent = node
    nodes = list(info)
    for n in nodes:
        if rng.random() < 0.5:
            tri.append((n, D, rng.choice(nodes)))

    def extend(depths):
        extra, new = [], {}
        for depth in depths:
            root = rng.choice(roots)
            parent = root
            for d in range(1, depth + 1):
                node = nm()
                extra += [(node, U, parent), (node, K, leafc if d == depth else rng.choice([mid1, mid2]))]
                new[node] = {"depth": d, "root": root}
                parent = node
        return extra, new
    return {"tri": tri, "info": info, "hidden": f"prog:rel:{U}>is:{K}:{tgt}|rel:{U}>self",
            "compose_rel": C, "extend": extend}


def world_cond(rng, nm):
    K, R1, R2 = nm(), nm(), nm()
    A, B, objc = nm(), nm(), nm()
    tri, info = [], {}

    def ent(cls):
        e, o1, o2 = nm(), nm(), nm()
        out = [(e, K, cls), (e, R1, o1), (e, R2, o2), (o1, K, objc), (o2, K, objc)]
        return e, out
    for i in range(12):
        e, t = ent(A if i % 2 == 0 else B)
        tri += t
        info[e] = {"depth": 1}

    def extend(_):
        extra, new = [], {}
        for i in range(4):
            e, t = ent(A if i % 2 == 0 else B)
            extra += t
            new[e] = {"depth": 1}
        return extra, new
    return {"tri": tri, "info": info, "hidden": f"prog:is:{K}:{A}>rel:{R1}|rel:{R2}", "extend": extend,
            "classes": {e: (A if (e, K, A) in tri else B) for e in info}}


def world_filter(rng, nm):
    K, R = nm(), nm()
    E, T, T2, T3 = nm(), nm(), nm(), nm()
    tri, info = [], {}

    def ent():
        e = nm()
        out = [(e, K, E)]
        for cls in [T, rng.choice([T2, T3]), rng.choice([T2, T3])]:
            o = nm()
            out += [(e, R, o), (o, K, cls)]
        return e, out
    for _ in range(9):
        e, t = ent()
        tri += t
        info[e] = {"depth": 1}

    def extend(_):
        extra, new = [], {}
        for _ in range(3):
            e, t = ent()
            extra += t
            new[e] = {"depth": 1}
        return extra, new
    return {"tri": tri, "info": info, "hidden": f"prog:rel:{R}>is:{K}:{T}", "extend": extend}


def classify(reply, s, name, t):
    got = reply.split()[2] if reply.startswith(f"{s} {name} ") else None
    prov = "[provisional]" in reply
    return {"s": s, "truth": t, "got": got, "provisional": prov, "reply": reply,
            "wrong_qualified": got is not None and got != t and not prov}


def current(state, name):
    st = json.loads(state.read_text())["state"]
    cap = st["capabilities"].get(name)
    ver = cap["versions"][cap["current"] - 1] if cap and cap.get("current") else None
    return st, ver


def teach_task(T, state, arm, arng, name, tri, hidden, lib, examples, sealed, values_pool):
    vals = [truth(tri, hidden, s, lib) for s in examples]
    if arm == "S":
        vals = [arng.choice([v for v in values_pool if v != t]) for t in vals]
    lines = [f"example {name}: {s} -> {v}" for s, v in zip(examples, vals)]
    status = T(*lines)[-1].split()[0]
    asked, pending, n = [], None, 0
    while n < QUESTIONS and status != "qualified":
        rr = T(*([pending] if pending else []), f"investigate {name}")
        n += 1
        if pending and pending.startswith("example"):
            status = rr[0].split()[0]
        pending = None
        q = rr[-1]
        if status == "qualified" or not q.startswith("what is "):
            break
        subj = q.split()[2]
        asked.append(subj)
        tv = truth(tri, hidden, subj, lib)
        if subj in sealed:
            pending = f"unanswered {name}: {subj}"  # withheld
            continue
        if tv is None:
            if arm in RICH:  # PX: not withheld, there is no single value; say which
                pending = f"example {name}: {subj} -> {'!none' if not truth_set(tri, hidden, subj, lib) else '!several'}"
            else:
                pending = f"unanswered {name}: {subj}"
            continue
        if arm == "S":
            tv = arng.choice([v for v in values_pool if v != tv])
        pending = f"example {name}: {subj} -> {tv}"
    if pending:
        T(pending)
    return [[s, v] for s, v in zip(examples, vals)], asked


def evaluate(T, name, tri, hidden, lib, items):
    pairs = [(s, truth(tri, hidden, s, lib)) for s in items]
    pairs = [(s, t) for s, t in pairs if t is not None]
    replies = T(*[f"what is {s} {name}" for s, _ in pairs]) if pairs else []
    return [classify(r, s, name, t) for (s, t), r in zip(pairs, replies)]


def abstain(T, name, tri, hidden, lib, exclude):
    """Items whose truth has no single value: a reply with a value is spurious (PX)."""
    ents = sorted({x for s_, _, o in tri for x in (s_, o)} - set(exclude))
    items = [e for e in ents if truth(tri, hidden, e, lib) is None]
    replies = T(*[f"what is {e} {name}" for e in items]) if items else []
    sp = [e for e, r in zip(items, replies) if r.startswith(f"{e} {name} ")]
    return {"n": len(items), "spurious": len(sp), "spurious_items": sp[:20]}


def run_arm(job):
    seed, arm, rounds = job
    rng = random.Random(seed)
    nm = Names(rng)
    arng = random.Random(seed * 31 + ord(arm))
    state = OUT / f"{arm}_{seed}.json"
    for p in OUT.glob(f"{arm}_{seed}.json*"):
        if p.is_dir():
            for q in p.iterdir():
                q.unlink()
            p.rmdir()
        else:
            p.unlink()
    log = []
    T = Teacher(state, ARMS[arm], log)
    tasks = []
    for rd in range(rounds):
        # T1 until (variable depth) and T4 composition with the acquired T1 capability
        W = world_until(rng, nm)
        tri = W["tri"]
        T(*[f"fact {s} {r} {o}" for s, r, o in tri])
        n1, n4 = nm(), nm()
        info = W["info"]
        d1 = [n for n, x in info.items() if x["depth"] == 1]
        d2 = [n for n, x in info.items() if x["depth"] == 2]
        ex1 = [rng.choice(d1), rng.choice(d2)]  # both example depths always present (dev fix, docs/G48.md)
        ex1.append(rng.choice([n for n in d1 + d2 if n not in ex1]))
        sealed1 = {n for n, x in info.items() if x["depth"] >= 3}
        roots = sorted({x["root"] for x in info.values()})
        for cls, name, hidden, lib, ex in (("T1", n1, W["hidden"], {}, ex1),):
            exs, asked = teach_task(T, state, arm, arng, name, tri, hidden, lib, ex, sealed1, roots)
            rows = evaluate(T, name, tri, hidden, lib, sorted(sealed1))
            extra, new = W["extend"]((6, 7))
            T(*[f"fact {s} {r} {o}" for s, r, o in extra])
            tri = tri + extra
            info.update(new)
            trows = evaluate(T, name, tri, hidden, lib, sorted(new))
            for r in rows + trows:
                r["depth"] = info[r["s"]]["depth"]
            st, ver = current(state, name)
            tasks.append({"round": rd, "class": cls, "name": name, "hidden": hidden, "examples": exs, "asked": asked,
                          "seq": ver["seq"] if ver else None, "status": ver["status"] if ver else "none",
                          "negative_statements": sum(str(v).startswith("!") for _, v in st["observations"].get(name, [])),
                          "hyp": {k: st["hypotheses"].get(name, {}).get(k) for k in ("searched_len", "supported_programs", "scan")},
                          "rows": rows + trows})
            if ABSTAIN:
                tasks[-1]["abstain"] = abstain(T, name, tri, hidden, lib, asked)
            sealed1 |= set(new)
        # T4: cap:n1 then the compose relation; examples at depth 1-2 (none sealed), sealed deeper
        st, ver1 = current(state, n1)
        lib = {"cap:T1": W["hidden"]}
        hidden4 = f"prog:cap:T1>rel:{W['compose_rel']}"
        # never a sealed item: the transfer chains are already in `info` and in sealed1 (verification N3)
        ex4 = [rng.choice([n for n, x in info.items() if x["depth"] == d and n not in sealed1]) for d in (1, 2)]
        caps = sorted({truth(tri, hidden4, s, lib) for s in info} - {None})
        exs, asked = teach_task(T, state, arm, arng, n4, tri, hidden4, lib, ex4, sealed1, caps)
        rows = evaluate(T, n4, tri, hidden4, lib, sorted(sealed1))
        for r in rows:
            r["depth"] = info[r["s"]]["depth"]
        st, ver = current(state, n4)
        tasks.append({"round": rd, "class": "T4", "name": n4, "hidden": hidden4.replace("cap:T1", f"cap:{n1}"),
                      "examples": exs, "asked": asked, "seq": ver["seq"] if ver else None,
                      "status": ver["status"] if ver else "none",
                      "uses_library": bool(ver) and any(f"cap:{n1}@" in t for t in ver["seq"]),
                      "negative_statements": sum(str(v).startswith("!") for _, v in st["observations"].get(n4, [])),
                          "hyp": {k: st["hypotheses"].get(n4, {}).get(k) for k in ("searched_len", "supported_programs", "scan")},
                      "rows": rows})
        if ABSTAIN:
            tasks[-1]["abstain"] = abstain(T, n4, tri, hidden4, lib, asked)
        # T2 conditional and T3 type-filtered
        for cls, maker, nex in (("T2", world_cond, 4), ("T3", world_filter, 3)):
            W = maker(rng, nm)
            tri = W["tri"]
            T(*[f"fact {s} {r} {o}" for s, r, o in tri])
            name = nm()
            ents = sorted(W["info"])
            if cls == "T2":
                a = [e for e in ents if W["classes"][e] == W["classes"][ents[0]]]
                b = [e for e in ents if e not in a]
                ex = rng.sample(a, 2) + rng.sample(b, 2)
            else:
                ex = rng.sample(ents, nex)
            sealed = set(ents) - set(ex)
            pool = sorted({truth(tri, W["hidden"], e, {}) for e in ents} - {None})
            exs, asked = teach_task(T, state, arm, arng, name, tri, W["hidden"], {}, ex, sealed, pool)
            rows = evaluate(T, name, tri, W["hidden"], {}, sorted(sealed))
            extra, new = W["extend"](None)
            T(*[f"fact {s} {r} {o}" for s, r, o in extra])
            tri = tri + extra
            trows = evaluate(T, name, tri, W["hidden"], {}, sorted(new))
            for r in rows + trows:
                r["depth"] = 1
            st, ver = current(state, name)
            tasks.append({"round": rd, "class": cls, "name": name, "hidden": W["hidden"], "examples": exs,
                          "asked": asked, "seq": ver["seq"] if ver else None, "status": ver["status"] if ver else "none",
                          "negative_statements": sum(str(v).startswith("!") for _, v in st["observations"].get(name, [])),
                          "hyp": {k: st["hypotheses"].get(name, {}).get(k) for k in ("searched_len", "supported_programs", "scan")},
                          "rows": rows + trows})
            if ABSTAIN:
                tasks[-1]["abstain"] = abstain(T, name, tri, W["hidden"], {}, asked)
    replies = [r for e in log for r in e["replies"]]
    return {"seed": seed, "arm": arm, "tasks": tasks, "processes": len(log),
            "cpu_s": round(sum(e["cpu_s"] for e in log), 3),
            "cpu_total_s": round(sum(e["cpu_total_s"] for e in log), 3),
            "replies_sha": __import__("hashlib").sha256("\n".join(replies).encode()).hexdigest(),
            "final_state_bytes": state.stat().st_size}


def _set_out(path):
    global OUT
    OUT = Path(path)


def acc(tasks, pred=lambda r: True):
    rows = [r for t in tasks for r in t["rows"] if pred(r)]
    return (round(sum(r["got"] == r["truth"] for r in rows) / len(rows), 4) if rows else None), len(rows)


def main(argv):
    seeds = SEEDS
    if "--seeds" in argv:
        seeds = [int(x) for x in argv[argv.index("--seeds") + 1].split(",")]
    rounds = 2
    global OUT
    if "--out" in argv:  # separate artifact dir per registered run (e.g. G48R)
        OUT = ROOT / "artifacts" / argv[argv.index("--out") + 1]
    OUT.mkdir(parents=True, exist_ok=True)
    sha0 = source_hash()
    with Pool(8, initializer=_set_out, initargs=(str(OUT),)) as pool:
        res = pool.map(run_arm, [(s, a, rounds) for s in seeds for a in ARMS])
    runs = {(r["seed"], r["arm"]): r for r in res}
    g = lambda a: [t for s in seeds for t in runs[(s, a)]["tasks"]]  # noqa: E731
    m = {}
    for a in ARMS:
        ts = g(a)
        m[a] = {"by_class": {c: dict(zip(("accuracy", "n"), acc([t for t in ts if t["class"] == c])))
                             for c in ("T1", "T2", "T3", "T4")},
                "T1_depth_ge3": dict(zip(("accuracy", "n"), acc([t for t in ts if t["class"] == "T1"], lambda r: r["depth"] >= 3))),
                "T1_depth_6_7_transfer": dict(zip(("accuracy", "n"), acc([t for t in ts if t["class"] == "T1"],
                                                                          lambda r: r["depth"] >= 6))),
                "all": dict(zip(("accuracy", "n"), acc(ts))),
                "T123": dict(zip(("accuracy", "n"), acc([t for t in ts if t["class"] in ("T1", "T2", "T3")]))),
                "wrong_qualified": sum(r["wrong_qualified"] for t in ts for r in t["rows"]),
                "qualified_tasks": sum(t["status"] == "qualified" for t in ts),
                "provisional_tasks": sum(t["status"] == "provisional" for t in ts),
                "answers_from_qualified": sum(1 for t in ts for r in t["rows"] if r["got"] is not None and not r["provisional"]),
                "status": [t["status"] for t in ts],
                "T4_library_uses": sum(t.get("uses_library", False) for t in ts if t["class"] == "T4"),
                "cpu_s": round(sum(runs[(s, a)]["cpu_s"] for s in seeds), 3),
                "cpu_total_s": round(sum(runs[(s, a)]["cpu_total_s"] for s in seeds), 3),
                "processes": sum(runs[(s, a)]["processes"] for s in seeds),
                "final_state_bytes": {s: runs[(s, a)]["final_state_bytes"] for s in seeds}}
    Pm = m["P"]
    th = {"H1_P_per_class_ge_0.95": all(v["accuracy"] is not None and v["accuracy"] >= 0.95 for v in Pm["by_class"].values()),
          "H2_P_T1_depth_ge3_ge_0.95": (Pm["T1_depth_ge3"]["accuracy"] or 0) >= 0.95,
          "H3_P_wrong_qualified_0": Pm["wrong_qualified"] == 0,
          "H4_X_T123_le_0.5": (m["X"]["T123"]["accuracy"] or 0) <= 0.5,
          "H5_S_all_le_0.10": (m["S"]["all"]["accuracy"] or 0) <= 0.10,
          "H6_A_replies_identical_to_P": all(runs[(s, "A")]["replies_sha"] == runs[(s, "P")]["replies_sha"] for s in seeds),
          "source_unchanged": sha0 == source_hash()}
    leaks = sorted({(t["class"], e[0]) for v in runs.values() for t in v["tasks"] for e in t["examples"]
                    if e[0] in {r["s"] for r in t["rows"]}})
    th["no_example_is_evaluated"] = not leaks
    rep = {"metrics": m, "thresholds": th, "all_pass": all(th.values()), "source_sha256": sha0,
           "engine_sha256": engine_hash(), "seeds": seeds, "example_leaks": leaks}
    name = "g48_dev" if "--dev" in argv else ("g48" if "--out" not in argv else argv[argv.index("--out") + 1])
    (OUT / f"{name}_receipt.json").write_text(json.dumps(rep, indent=1))
    (OUT / f"{name}_raw.json").write_text(json.dumps({f"{k[0]}:{k[1]}": v for k, v in runs.items()}))
    print(json.dumps({"thresholds": th, "P": {k: Pm[k] for k in ("by_class", "T1_depth_ge3", "wrong_qualified", "qualified_tasks")},
                      "X": m["X"]["T123"], "S": m["S"]["all"],
                      "cpu_total_s": {a: m[a]["cpu_total_s"] for a in ARMS}}, indent=1))
    return 0 if rep["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
