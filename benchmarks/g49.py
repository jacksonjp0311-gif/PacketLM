"""G49: scoped closed-world teacher statements (`complete X`) and a T1 redesign where depth 3 is
answerable and depth >= 4 sealed (docs/G49.md, registered before the run).
Arms (all on G48-style worlds, programs mode, exact scan):
  P  standard teacher (values only; withheld when there is no single value)
  R  P + `!none`/`!several` statements (PX teacher)
  F  R + `complete S` for every subject the teacher answers (honest: S's closure is fully told)
  N  R + `complete E` for as many entities nobody is asked about (scope control: must change nothing)
  L  F, but one fact of each example subject's closure is withheld while `complete` is stated
     (lying / incomplete-facts teacher); the facts are revealed after a first ("window") evaluation
  L0 L's withheld facts and reveal, no `complete` statements (open-world baseline for L)
Run: python3 benchmarks/g49.py [--seeds ...] [--out g49] [--dev]
"""

from __future__ import annotations
import hashlib
import json
import random
import subprocess
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT))
import g48  # noqa: E402
from g48 import truth, truth_set, classify, current, world_until, world_cond, world_filter  # noqa: E402
from packetlm.g45_test import Names, Teacher, source_hash  # noqa: E402

ARMS = {"P": ["--programs"], "R": ["--programs", "--answers"], "F": ["--programs", "--answers"],
        "N": ["--programs", "--answers"], "L": ["--programs", "--answers"], "L0": ["--programs", "--answers"]}
RICH = {"R", "F", "N", "L", "L0"}
COMPLETE = {"F", "L"}
WITHHOLD = {"L", "L0"}
SEEDS = [531, 532, 533, 534, 535, 536, 537]
QUESTIONS = 6
SEAL_DEPTH = 4  # T1: depth 1-3 askable, depth >= 4 sealed (G49 T1 redesign)
OUT = ROOT / "artifacts/g49"


def closure(tri, x):
    adj = {}
    for s, _, o in tri:
        adj.setdefault(s, set()).add(o)
    seen, todo = {x}, [x]
    while todo:
        for z in adj.get(todo.pop(), ()):
            if z not in seen:
                seen.add(z)
                todo.append(z)
    return seen


def withhold(rng, tri, subjects):
    """One told fact inside each subject's closure (sorted, seeded draw); shared draws dedupe."""
    out = []
    for s in subjects:
        clo = closure(tri, s)
        cand = sorted(t for t in tri if t[0] in clo and t not in out)
        if cand:
            out.append(rng.choice(cand))
    return out


def teach_task(T, state, arm, name, tri, hidden, lib, examples, sealed, scope_pool, srng):
    """Values from the full world. F/L: `complete s` after every answered subject. N: as many
    `complete e` statements, about entities never asked (scope control)."""
    vals = [truth(tri, hidden, s, lib) for s in examples]
    lines = [f"example {name}: {s} -> {v}" for s, v in zip(examples, vals)]
    said = []

    def comp(subjs):
        if arm in COMPLETE:
            said.extend(subjs)
            return [f"complete {' '.join(subjs)}"]
        if arm == "N":
            pool = [e for e in scope_pool if e not in said]
            pick = srng.sample(pool, min(len(subjs), len(pool)))
            said.extend(pick)
            return [f"complete {' '.join(pick)}"] if pick else []
        return []
    T(*(lines + comp(examples)))
    asked, n = [], 0
    while n < QUESTIONS:
        _, ver = current(state, name)
        if ver and ver["status"] == "qualified":
            break
        q = T(f"investigate {name}")[-1]
        n += 1
        if not q.startswith("what is "):
            break
        subj = q.split()[2]
        asked.append(subj)
        tv = truth(tri, hidden, subj, lib)
        if subj in sealed:
            T(f"unanswered {name}: {subj}")
            continue
        if tv is None:
            if arm in RICH:
                st = "!none" if not truth_set(tri, hidden, subj, lib) else "!several"
                T(f"example {name}: {subj} -> {st}", *comp([subj]))
            else:
                T(f"unanswered {name}: {subj}")
            continue
        T(f"example {name}: {subj} -> {tv}", *comp([subj]))
    return [[s, v] for s, v in zip(examples, vals)], asked, said


def evaluate(T, name, tri, hidden, lib, items):
    pairs = [(s, truth(tri, hidden, s, lib)) for s in items]
    pairs = [(s, t) for s, t in pairs if t is not None]
    replies = T(*[f"what is {s} {name}" for s, _ in pairs]) if pairs else []
    return [classify(r, s, name, t) for (s, t), r in zip(pairs, replies)]


def abstain(T, name, tri, hidden, lib, exclude):
    ents = sorted({x for s_, _, o in tri for x in (s_, o)} - set(exclude))
    items = [e for e in ents if truth(tri, hidden, e, lib) is None]
    replies = T(*[f"what is {e} {name}" for e in items]) if items else []
    sp = [e for e, r in zip(items, replies) if r.startswith(f"{e} {name} ")]
    return {"n": len(items), "spurious": len(sp), "items": items, "spurious_items": sp}


def run_arm(job):
    seed, arm, rounds = job
    rng = random.Random(seed)
    nm = Names(rng)
    srng = random.Random(seed * 131 + sum(map(ord, arm)))
    wrng = random.Random(seed * 17 + 3)  # same withheld facts in L and L0
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
    said_all = []  # every `complete` statement of this run so far (a statement is about the world)

    def finish(cls, name, tri, hidden, lib, exs, asked, said, rows, window, held, extra=None):
        st, ver = current(state, name)
        stj = json.loads(state.read_text())["state"]
        rec = {"round": rd, "class": cls, "name": name, "hidden": hidden, "examples": exs, "asked": asked,
               "complete_said": said, "withheld": [list(t) for t in held],
               # statements that were false when made: a withheld fact has its subject in the closure
               "complete_false": [x for x in said if any(h[0] in closure(tri, x) for h in held)],
               "seq": ver["seq"] if ver else None, "status": ver["status"] if ver else "none",
               "observations": st["observations"].get(name, []),
               "negative_statements": sum(str(v).startswith("!") for _, v in st["observations"].get(name, [])),
               "complete_log": [e for e in stj.get("complete_log", []) if e["x"] in said],
               "complete_active": sorted(x for x in stj.get("complete", {}) if x in said),
               "hyp": {k: st["hypotheses"].get(name, {}).get(k) for k in ("searched_len", "supported_programs", "scan")},
               "rows": rows, "window_rows": window}
        rec.update(extra or {})
        said_all.extend(said)
        rec["touched"] = bool({o[0] for o in rec["observations"]} & set(said_all))
        if cls == "T4":  # depends on the T1 capability of the same world
            rec["touched"] = rec["touched"] or tasks[-1]["touched"]
        tasks.append(rec)

    for rd in range(rounds):
        W = world_until(rng, nm)
        tri, info = W["tri"], W["info"]
        n1, n4 = nm(), nm()
        d1 = [n for n, x in info.items() if x["depth"] == 1]
        d2 = [n for n, x in info.items() if x["depth"] == 2]
        ex1 = [rng.choice(d1), rng.choice(d2)]
        ex1.append(rng.choice([n for n in d1 + d2 if n not in ex1]))
        sealed1 = {n for n, x in info.items() if x["depth"] >= SEAL_DEPTH}
        held = withhold(wrng, tri, ex1) if arm in WITHHOLD else []
        T(*[f"fact {s} {r} {o}" for s, r, o in tri if (s, r, o) not in held])
        ents = sorted({x for s_, _, o in tri for x in (s_, o)})
        scope = [e for e in ents if e not in sealed1 and e not in ex1]
        exs, asked, said = teach_task(T, state, arm, n1, tri, W["hidden"], {}, ex1, sealed1, scope, srng)
        window = evaluate(T, n1, tri, W["hidden"], {}, sorted(sealed1)) if held else None
        if held:
            T(*[f"fact {s} {r} {o}" for s, r, o in held])  # reveal: falsifies the lying statements
        rows = evaluate(T, n1, tri, W["hidden"], {}, sorted(sealed1))
        extra, new = W["extend"]((6, 7))
        T(*[f"fact {s} {r} {o}" for s, r, o in extra])
        tri = tri + extra
        info.update(new)
        trows = evaluate(T, n1, tri, W["hidden"], {}, sorted(new))
        for r in rows + trows + (window or []):
            r["depth"] = info[r["s"]]["depth"]
        finish("T1", n1, tri, W["hidden"], {}, exs, asked, said, rows + trows, window, held,
               {"abstain": abstain(T, n1, tri, W["hidden"], {}, [e for e, _ in exs] + asked)})
        sealed1 |= set(new)
        lib = {"cap:T1": W["hidden"]}
        hidden4 = f"prog:cap:T1>rel:{W['compose_rel']}"
        ex4 = [rng.choice([n for n, x in info.items() if x["depth"] == d and n not in sealed1]) for d in (1, 2)]
        held4 = []  # T4 reuses the T1 world, already told in full: no withholding (docs/G49.md)
        scope4 = [e for e in sorted({x for s_, _, o in tri for x in (s_, o)}) if e not in sealed1 and e not in ex4]
        exs, asked, said = teach_task(T, state, arm, n4, tri, hidden4, lib, ex4, sealed1, scope4, srng)
        window = evaluate(T, n4, tri, hidden4, lib, sorted(sealed1)) if held4 else None
        if held4:
            T(*[f"fact {s} {r} {o}" for s, r, o in held4])
        rows = evaluate(T, n4, tri, hidden4, lib, sorted(sealed1))
        for r in rows + (window or []):
            r["depth"] = info[r["s"]]["depth"]
        st, ver = current(state, n4)
        finish("T4", n4, tri, hidden4.replace("cap:T1", f"cap:{n1}"), lib, exs, asked, said, rows, window, held4,
               {"uses_library": bool(ver) and any(f"cap:{n1}@" in t for t in ver["seq"]),
                "abstain": abstain(T, n4, tri, hidden4, lib, [e for e, _ in exs] + asked)})
        for cls, maker, nex in (("T2", world_cond, 4), ("T3", world_filter, 3)):
            W = maker(rng, nm)
            tri = W["tri"]
            name = nm()
            ents = sorted(W["info"])
            if cls == "T2":
                a = [e for e in ents if W["classes"][e] == W["classes"][ents[0]]]
                b = [e for e in ents if e not in a]
                ex = rng.sample(a, 2) + rng.sample(b, 2)
            else:
                ex = rng.sample(ents, nex)
            sealed = set(ents) - set(ex)
            held = withhold(wrng, tri, ex) if arm in WITHHOLD else []
            T(*[f"fact {s} {r} {o}" for s, r, o in tri if (s, r, o) not in held])
            allents = sorted({x for s_, _, o in tri for x in (s_, o)})
            scope = [e for e in allents if e not in sealed and e not in ex]
            exs, asked, said = teach_task(T, state, arm, name, tri, W["hidden"], {}, ex, sealed, scope, srng)
            window = evaluate(T, name, tri, W["hidden"], {}, sorted(sealed)) if held else None
            if held:
                T(*[f"fact {s} {r} {o}" for s, r, o in held])
            rows = evaluate(T, name, tri, W["hidden"], {}, sorted(sealed))
            extra, new = W["extend"](None)
            T(*[f"fact {s} {r} {o}" for s, r, o in extra])
            tri = tri + extra
            trows = evaluate(T, name, tri, W["hidden"], {}, sorted(new))
            for r in rows + trows + (window or []):
                r["depth"] = 1
            finish(cls, name, tri, W["hidden"], {}, exs, asked, said, rows + trows, window, held,
                   {"abstain": abstain(T, name, tri, W["hidden"], {}, [e for e, _ in exs] + asked)})
    replies = [r for e in log for r in e["replies"]]
    return {"seed": seed, "arm": arm, "tasks": tasks, "processes": len(log),
            "cpu_s": round(sum(e["cpu_s"] for e in log), 3),
            "cpu_total_s": round(sum(e["cpu_total_s"] for e in log), 3),
            "replies_sha": hashlib.sha256("\n".join(replies).encode()).hexdigest(),
            "final_state_bytes": state.stat().st_size}


def _set_out(path):
    global OUT
    OUT = Path(path)


def acc(rows):
    return (round(sum(r["got"] == r["truth"] for r in rows) / len(rows), 4) if rows else None), len(rows)


def metrics(ts):
    rows = lambda pred=lambda t, r: True: [r for t in ts for r in t["rows"] if pred(t, r)]  # noqa: E731
    m = {"by_class": {c: dict(zip(("accuracy", "n"), acc(rows(lambda t, r, c=c: t["class"] == c)))) for c in ("T1", "T2", "T3", "T4")},
         "T1_depth_ge4": dict(zip(("accuracy", "n"), acc(rows(lambda t, r: t["class"] == "T1" and r["depth"] >= SEAL_DEPTH)))),
         "wrong_qualified": sum(r["wrong_qualified"] for r in rows()),
         "qualified_tasks": sum(t["status"] == "qualified" for t in ts),
         "qualified_by_class": {c: sum(t["status"] == "qualified" for t in ts if t["class"] == c) for c in ("T1", "T2", "T3", "T4")},
         "status": [t["status"] for t in ts],
         "T1_asked_depth3": sum(1 for t in ts if t["class"] == "T1" for s in t["asked"] if s),
         "scans": [t["hyp"]["scan"]["complete"] for t in ts if t["hyp"].get("scan")],
         "spurious": {"n": sum(t["abstain"]["n"] for t in ts), "spurious": sum(t["abstain"]["spurious"] for t in ts)},
         "spurious_excl_T1": {"n": sum(t["abstain"]["n"] for t in ts if t["class"] != "T1"),
                              "spurious": sum(t["abstain"]["spurious"] for t in ts if t["class"] != "T1")}}
    win = [r for t in ts for r in (t["window_rows"] or [])]
    if win:
        m["window"] = {"accuracy": acc(win)[0], "n": len(win), "wrong_qualified": sum(r["wrong_qualified"] for r in win),
                       "qualified_answers": sum(1 for r in win if r["got"] is not None and not r["provisional"])}
    return m


def main(argv):
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    # verification L1 of b2bb9b8: record a dirty tree and the harness hash in the receipt
    dirty_tree = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    import hashlib
    harness = hashlib.sha256(b"".join((ROOT / f).read_bytes() for f in ["benchmarks/g49.py", "benchmarks/g48.py", "packetlm/g45_test.py"])).hexdigest()
    seeds = [int(x) for x in argv[argv.index("--seeds") + 1].split(",")] if "--seeds" in argv else SEEDS
    global OUT
    name = "g49_dev" if "--dev" in argv else (argv[argv.index("--out") + 1] if "--out" in argv else "g49")
    OUT = ROOT / "artifacts" / name
    OUT.mkdir(parents=True, exist_ok=True)
    sha0 = source_hash()
    with Pool(8, initializer=_set_out, initargs=(str(OUT),)) as pool:
        res = pool.map(run_arm, [(s, a, 2) for s in seeds for a in ARMS])
    runs = {(r["seed"], r["arm"]): r for r in res}
    g = lambda a: [t for s in seeds for t in runs[(s, a)]["tasks"]]  # noqa: E731
    m = {a: metrics(g(a)) for a in ARMS}
    for a in ARMS:
        m[a]["cpu_total_s"] = round(sum(runs[(s, a)]["cpu_total_s"] for s in seeds), 3)
    F, R, N, L = g("F"), g("R"), g("N"), g("L")
    # every `complete` statement of L that was false when made is retracted once the fact is revealed
    false_said = sum(len(t["complete_false"]) for t in L)
    retracted = sum(any(e["x"] == x for e in t["complete_log"]) for t in L for x in t["complete_false"])
    untouched = sum(not t["touched"] for t in N)
    untouched_same = sum(not tn["touched"] and (tn["status"], tn["seq"], tn["asked"]) == (tr["status"], tr["seq"], tr["asked"])
                         for tn, tr in zip(N, R))
    leaks = sorted({(t["class"], s) for a in ARMS for t in g(a) for s in [o[0] for o in t["observations"]]
                    if s in {r["s"] for r in t["rows"]} | {r["s"] for r in (t["window_rows"] or [])}})
    th = {"G49_exact_scans_complete": all(all(m[a]["scans"]) and m[a]["scans"] for a in ARMS),
          "FC1_F_wrong_qualified_0": m["F"]["wrong_qualified"] == 0,
          "FC2_F_qualifies_ge_25pct_and_more_than_R": m["F"]["qualified_tasks"] > m["R"]["qualified_tasks"]
          and m["F"]["qualified_tasks"] >= 0.25 * len(F),
          # scope control: a task none of whose observed subjects was stated complete (and, for T4,
          # whose T1 was not) is identical to R: same questions, program and status
          "FC3_N_untouched_tasks_equal_R": untouched >= 0.25 * len(N) and untouched_same == untouched,
          "FC4_L_false_statements_retracted": false_said > 0 and retracted == false_said,
          "FC5_L_wrong_qualified_after_reveal_0": m["L"]["wrong_qualified"] == 0,
          "D1_R_T1_depth_ge4_ge_0.95": (m["R"]["T1_depth_ge4"]["accuracy"] or 0) >= 0.95,
          "D2_F_T1_depth_ge4_ge_0.95": (m["F"]["T1_depth_ge4"]["accuracy"] or 0) >= 0.95,
          "no_observed_subject_is_evaluated": not leaks,
          "source_unchanged": sha0 == source_hash()}
    rep = {"started": started, "head": head, "metrics": m, "thresholds": th, "all_pass": all(th.values()),
           "lying": {"false_statements": false_said, "retracted": retracted},
           "scope_control": {"untouched": untouched, "untouched_same": untouched_same, "tasks": len(N),
                             "statuses_equal_all": [t["status"] for t in N] == [t["status"] for t in R]},
           "source_sha256": sha0, "engine_sha256": g48.engine_hash(), "seeds": seeds, "leaks": leaks,
           "git_status_porcelain": dirty_tree, "harness_sha256": harness}
    (OUT / f"{name}_receipt.json").write_text(json.dumps(rep, indent=1))
    (OUT / f"{name}_raw.json").write_text(json.dumps({f"{k[0]}:{k[1]}": v for k, v in runs.items()}))
    print(json.dumps({"thresholds": th, "lying": rep["lying"], "scope_control": rep["scope_control"],
                      "summary": {a: {k: m[a][k] for k in ("by_class", "T1_depth_ge4", "wrong_qualified", "qualified_tasks",
                                                          "qualified_by_class", "spurious", "spurious_excl_T1", "cpu_total_s")}
                                  | ({"window": m[a]["window"]} if "window" in m[a] else {}) for a in ARMS}}, indent=1))
    return 0 if rep["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
