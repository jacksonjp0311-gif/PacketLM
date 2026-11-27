"""G46 longitudinal continual-learning benchmark. Protocol: docs/G46.md.

The harness is the teacher and holds the hidden programs. Every engine call is
a new process through the controlled-language CLI. Writes artifacts/g46/.
Run: python benchmarks/g46.py [--seeds 11,22,33] [--jobs 8]
"""

from __future__ import annotations
import json
import random
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from packetlm import reference  # noqa: E402
from packetlm.g45_test import Names, Teacher, functional, source_hash  # noqa: E402

OUT = ROOT / "artifacts/g46"
SPEC = {
    "A": {"rels": "abcd", "layers": 5, "width": 10, "missing": 0.0, "ambig": False, "sealed_from": 5,
          "tasks": ["ab", "abc", "abca", "bb", "bbab", "dab"]},
    "B": {"rels": "abcdef", "layers": 7, "width": 8, "missing": 0.15, "ambig": True, "sealed_from": 4,
          "tasks": ["ab", "abc", "ef", "efab", "cd", "cdabc"]},
}
FLAGS = {"C": [], "B": ["--no-library"], "P": ["--no-library"], "F": [], "S": [],
         "G": ["--no-geometry"], "N": ["--no-activation"]}
CLI_ARMS = list(FLAGS)


def truth(triples, hidden, s):
    out = reference.run(reference.index(triples), hidden, s)
    if not out:
        return ("undef",)
    return ("val", next(iter(out))) if len(out) == 1 else ("amb", tuple(sorted(out)))


def graph(rng, nm, spec, width, rel, missing, ambig):
    L = [[nm() for _ in range(width)] for _ in range(spec["layers"])]
    triples = []
    for c in spec["rels"]:
        for k in range(spec["layers"] - 1):
            triples += [(s, rel[c], o) for s, o in functional(rng, L[k], L[k + 1])]
    if missing:
        triples = [t for t in triples if rng.random() >= missing]
    if ambig:
        for k in range(spec["layers"] - 1):
            s, c = rng.choice(L[k]), rng.choice(spec["rels"])
            have = {o for x, r, o in triples if x == s and r == rel[c]}
            o2 = rng.choice([o for o in L[k + 1] if o not in have])
            triples.append((s, rel[c], o2))
    return L, triples


def world(seed):
    rng = random.Random(seed)
    nm = Names(rng)
    fams = []
    for fi, phase in enumerate("AAABBB"):
        spec = SPEC[phase]
        rel = {c: nm() for c in spec["rels"]}
        L, triples = graph(rng, nm, spec, spec["width"], rel, spec["missing"], spec["ambig"])
        pool, sealed = L[0][:spec["sealed_from"]], L[0][spec["sealed_from"]:]
        tasks = []
        for ti, shape in enumerate(spec["tasks"]):
            hidden = [rel[c] for c in shape]
            single = [s for s in pool + L[1] if truth(triples, hidden, s)[0] == "val"]
            ex = single[:2]
            t = {"name": nm(), "shape": shape, "hidden": hidden, "examples": ex}
            if phase == "B" and fi == 3 and ti == 1 and len(ex) == 2:
                v0, v1 = truth(triples, hidden, ex[0])[1], truth(triples, hidden, ex[1])[1]
                wrong = v1 if v1 != v0 else next(o for o in L[-1] if o != v0)
                t["contradiction"] = wrong
            tasks.append(t)
        fam = {"phase": phase, "rel": rel, "layers": L, "triples": triples, "pool": pool, "sealed": sealed, "tasks": tasks}
        if phase == "A":
            s, r = L[1][3], rel["a"]
            old = {o for x, rr, o in triples if x == s and rr == r}
            fam["correction"] = (s, r, rng.choice([o for o in L[2] if o not in old]))
        TL, tt = graph(rng, nm, spec, 6, rel, 0.0, False)
        fam["transfer"] = {"subjects": TL[0], "triples": tt}
        fams.append(fam)
    return fams


def sealed_tokens(fams):
    out = set()
    for f in fams:
        out |= set(f["sealed"])
        for layer in [f["transfer"]["subjects"]]:
            out |= set(layer)
        out |= {s for s, _, o in f["transfer"]["triples"]} | {o for _, _, o in f["transfer"]["triples"]}
    return out


def classify(reply, s, name, t):
    got = None
    if reply.startswith(f"{s} {name} "):
        got = reply.split()[2]
    amb = reply.startswith("ambiguous")
    prov = "[provisional]" in reply
    if t[0] == "val":
        ok = got == t[1]
    elif t[0] == "amb":
        ok = amb
    else:
        ok = got is None and not amb
    norm = got if got is not None else ("AMB" if amb else None)
    return {"s": s, "name": name, "truth": list(t), "reply": reply, "norm": norm, "ok": ok, "provisional": prov,
            "wrong_qualified": got is not None and t[0] == "val" and got != t[1] and not prov,
            "spurious": t[0] == "undef" and got is not None}


def ask(T, items):
    if not items:
        return []
    replies = T(*[f"what is {s} {n}" for s, n, _ in items])
    return [classify(r, s, n, t) for (s, n, t), r in zip(items, replies)]


def cap_of(state_path, name):
    st = json.loads(Path(state_path).read_text())["state"]
    cap = st["capabilities"].get(name)
    ver = cap["versions"][cap["current"] - 1] if cap and cap.get("current") else None
    return ver, st["hypotheses"].get(name, {}), Path(state_path).stat().st_size


def expand_base(state_path, seq):
    st = json.loads(Path(state_path).read_text())["state"]

    def ex(sq):
        out = []
        for step in sq:
            if step.startswith("rel:"):
                out.append(step[4:])
            else:
                n, v = step[4:].rsplit("@", 1)
                out += ex(st["capabilities"][n]["versions"][int(v) - 1]["seq"])
        return out
    return ex(seq)


def stat_sum(log, a, b):
    out = {"evaluations": 0, "executions": 0, "row_ops": 0, "asks": 0}
    for e in log[a:b]:
        for k in out:
            out[k] += e["stats"].get(k, 0)
    out["cpu_s"] = round(sum(e["cpu_s"] for e in log[a:b]), 4)
    out["wall_s"] = round(sum(e["wall_s"] for e in log[a:b]), 3)
    out["processes"] = b - a
    out["lines"] = sum(len(e["lines"]) for e in log[a:b])
    return out


def run_arm(args):
    seed, arm = args
    fams = world(seed)
    sealed_all = sealed_tokens(fams)
    d = OUT / f"seed{seed}"
    d.mkdir(parents=True, exist_ok=True)
    persistent = d / f"{arm}.json"
    for p in d.glob(f"{arm}*.json*"):
        p.unlink()
    flags = FLAGS[arm] + ["--deepen=5"]
    rng = random.Random(seed * 7919 + ord(arm))
    log, tasks, families, last = [], [], [], {}
    for fi, fam in enumerate(fams):
        triples = list(fam["triples"])
        frozen = arm == "F" and fam["phase"] == "B"
        fam_items = []
        for ti, task in enumerate(fam["tasks"]):
            name, ex = task["name"], task["examples"]
            state = d / f"B_{fi}_{ti}.json" if arm == "B" else persistent
            T = Teacher(state, flags, log)
            a0 = len(log)
            evidence, asked, status = [], [], None
            if not frozen:
                lines = []
                if arm == "B" or ti == 0:
                    lines += [f"fact {s} {r} {o}" for s, r, o in triples]
                vals = [truth(triples, task["hidden"], s)[1] for s in ex]
                if arm == "S":
                    vals = vals[1:] + vals[:1]
                first = list(vals)
                if task.get("contradiction") and arm != "S":
                    first[0] = task["contradiction"]
                lines += [f"example {name}: {s} -> {v}" for s, v in zip(ex, first)]
                rr = T(*lines)
                status = rr[-1].split()[0] if ex else None
                if task.get("contradiction") and arm != "S":
                    msg = T(f"correct example {name}: {ex[0]} -> {vals[0]}")[0]
                    status = msg.split("; ")[1].split()[0]
                evidence = [[s, v] for s, v in zip(ex, vals)]
                pending, n = None, 0
                while n < 4 and status != "qualified" and ex:
                    rr = T(*([pending] if pending else []), f"investigate {name}")
                    n += 1
                    if pending and pending.startswith("example"):
                        status = rr[0].split()[0]
                    pending = None
                    if status == "qualified":
                        break
                    q = rr[-1]
                    if not q.startswith("what is "):
                        break
                    subj = q.split()[2]
                    asked.append(subj)
                    tv = truth(triples, task["hidden"], subj)
                    if subj in sealed_all or tv[0] != "val":
                        pending = f"unanswered {name}: {subj}"
                        continue
                    val = tv[1]
                    if arm == "S":
                        others = [o for o in L0_values(fam, triples, task) if o != val]
                        val = rng.choice(others) if others else val
                    evidence.append([subj, val])
                    pending = f"example {name}: {subj} -> {val}"
                if pending:
                    rr = T(pending)
                    if pending.startswith("example"):
                        status = rr[0].split()[0]
            items = [(s, name, truth(triples, task["hidden"], s)) for s in fam["sealed"]]
            rows = ask(T, items)
            a1 = len(log)
            ver, hyp, size = cap_of(state, name) if state.exists() else (None, {}, 0)
            base = expand_base(state, ver["seq"]) if ver else None
            acquired = bool(ver) and ver["status"] in ("qualified", "provisional") and base == task["hidden"]
            for r in rows:
                last[(r["s"], r["name"])] = r
            fam_items += items
            tasks.append({"family": fi, "phase": fam["phase"], "task": ti, "shape": task["shape"], "name": name,
                          "status": ver["status"] if ver else status, "seq": ver["seq"] if ver else None,
                          "uses_library": bool(ver) and any(x.startswith("cap:") for x in ver["seq"]),
                          "acquired": acquired, "evidence": evidence, "asked": asked,
                          "searched_len": hyp.get("searched_len"), "pruned": hyp.get("pruned"),
                          "correct": sum(r["ok"] for r in rows), "n_sealed": len(rows), "rows": rows,
                          "cost": stat_sum(log, a0, a1), "state_bytes": size})
        fam_rec = {"family": fi, "phase": fam["phase"]}
        if arm != "B":
            T = Teacher(persistent, flags, log)
            a0 = len(log)
            if fam["phase"] == "A":
                s, r, o = fam["correction"]
                fam_rec["correction_reply"] = T(f"correct {s} {r} {o}")[0]
                old_truth = {(s_, n_): t_ for s_, n_, t_ in fam_items}
                triples = [(x, y, z) for x, y, z in triples if not (x == s and y == r)] + [(s, r, o)]
                fam_items = [(s_, n_, truth(triples, next(t for t in fam["tasks"] if t["name"] == n_)["hidden"], s_))
                             for s_, n_, _ in fam_items]
                rows = ask(T, fam_items)
                changed = [r_ for r_ in rows if tuple(r_["truth"]) != old_truth[(r_["s"], r_["name"])]]
                fam_rec["correction"] = {"affected": len(changed), "propagated": sum(r_["ok"] for r_ in changed),
                                         "rows": changed}
                for r_ in rows:
                    if tuple(r_["truth"]) == old_truth[(r_["s"], r_["name"])]:
                        prev = last[(r_["s"], r_["name"])]
                        fam_rec.setdefault("post_correction_unchanged", []).append(prev["norm"] == r_["norm"])
                    last[(r_["s"], r_["name"])] = r_
            tr = fam["transfer"]
            if not frozen:
                T(*[f"fact {s} {r} {o}" for s, r, o in tr["triples"]])
            titems = [(s, t["name"], truth(tr["triples"], t["hidden"], s)) for t in fam["tasks"] for s in tr["subjects"]]
            trows = ask(T, titems)
            fam_rec["transfer"] = {"correct": sum(r_["ok"] for r_ in trows), "n": len(trows),
                                   "wrong_qualified": sum(r_["wrong_qualified"] for r_ in trows)}
            for r_ in trows:
                last[(r_["s"], r_["name"])] = r_
            keys = list(last)
            rows = ask(T, [(s_, n_, tuple(last[(s_, n_)]["truth"])) for s_, n_ in keys])
            same = [r_["norm"] == last[(r_["s"], r_["name"])]["norm"] for r_ in rows]
            fam_rec["retention"] = {"n": len(same), "unchanged": sum(same),
                                    "changed": [r_ for r_, k in zip(rows, same) if not k]}
            for r_ in rows:
                last[(r_["s"], r_["name"])] = r_
            fam_rec["cost"] = stat_sum(log, a0, len(log))
        families.append(fam_rec)
    lines = sum(len(e["lines"]) for e in log)
    return {"seed": seed, "arm": arm, "flags": flags, "tasks": tasks, "families": families,
            "interactions": lines, "processes": len(log), "final_state_bytes":
            persistent.stat().st_size if persistent.exists() else None}


def L0_values(fam, triples, task):
    return sorted({truth(triples, task["hidden"], s)[1] for s in fam["pool"]
                   if truth(triples, task["hidden"], s)[0] == "val"})


def run_reference(seed, c_run):
    fams = world(seed)
    out = []
    for t in c_run["tasks"]:
        fam = fams[t["family"]]
        task = fam["tasks"][t["task"]]
        triples = list(fam["triples"])
        t0 = time.process_time()
        prog, evaluated = reference.learn(triples, [tuple(e) for e in t["evidence"]], max_len=5) if t["evidence"] else (None, 0)
        cpu = time.process_time() - t0
        rows = []
        for s in fam["sealed"]:
            tv = truth(triples, task["hidden"], s)
            got = reference.run(reference.index(triples), prog, s) if prog else set()
            rows.append({"truth": list(tv), "ok": (tv[0] == "val" and got == {tv[1]}) or (tv[0] == "amb" and len(got) > 1)
                         or (tv[0] == "undef" and not got)})
        out.append({"family": t["family"], "task": t["task"], "acquired": prog == task["hidden"], "program": prog,
                    "evaluated": evaluated, "cpu_s": round(cpu, 4), "correct": sum(r["ok"] for r in rows), "n_sealed": len(rows)})
    return out


def amort(c, b, extra=0.0):
    out, cc, cb, equal = [], 0.0, 0.0, True
    for i, (x, y) in enumerate(zip(c["tasks"], b["tasks"])):
        cc += x["cost"]["cpu_s"]
        cb += y["cost"]["cpu_s"]
        equal = equal and x["correct"] == y["correct"]
        out.append({"n": i + 1, "C": round(cc, 4), "base": round(cb, 4), "equal_accuracy": equal,
                    "A": round(1 - cc / cb, 4) if equal and cb else None})
    if extra and out:
        last = out[-1]
        last["A_with_overhead"] = round(1 - (cc + extra) / cb, 4) if last["equal_accuracy"] else None
    return out


def evaluate(runs, seeds, sha0, sha1, sealed_ok):
    rep = {"engine_sha256_start": sha0, "engine_sha256_end": sha1, "sealed_tokens_absent_from_trained_state": sealed_ok,
           "seeds": {}}
    allpass = sha0 == sha1 and sealed_ok
    for seed in seeds:
        R = {a: runs[(seed, a)] for a in CLI_ARMS}
        C = R["C"]
        fams = [f for f in C["families"]]
        ret_n = sum(f["retention"]["n"] for f in fams)
        ret_u = sum(f["retention"]["unchanged"] for f in fams)
        rows = [r for t in C["tasks"] for r in t["rows"]]
        amb = [r for r in rows if r["truth"][0] == "amb"]
        corr = [f["correction"] for f in fams if "correction" in f]
        tr_c = sum(f["transfer"]["correct"] for f in fams)
        tr_n = sum(f["transfer"]["n"] for f in fams)
        overhead = sum(f["cost"]["cpu_s"] for f in fams)
        B_phase = lambda run: [t for t in run["tasks"] if t["phase"] == "B"]
        m = {
            "retention": round(ret_u / max(ret_n, 1), 4),
            "plasticity": round(sum(t["acquired"] for t in C["tasks"]) / len(C["tasks"]), 4),
            "transfer": round(tr_c / max(tr_n, 1), 4),
            "wrong_qualified_sealed": sum(r["wrong_qualified"] for r in rows),
            "correction_affected": sum(c["affected"] for c in corr),
            "correction_propagated": sum(c["propagated"] for c in corr),
            "spurious_on_undefined": sum(r["spurious"] for r in rows),
            "undefined_queries": sum(r["truth"][0] == "undef" for r in rows),
            "ambiguous_queries": len(amb), "ambiguous_replies": sum(r["ok"] for r in amb),
            "interactions": C["interactions"], "processes": C["processes"],
            "frozen_phaseB_acquired": round(sum(t["acquired"] for t in B_phase(R["F"])) / 18, 4),
            "shuffled_match": round(sum(t["acquired"] for t in R["S"]["tasks"]) / 36, 4),
            "geometry_disabled_same": [t["acquired"] for t in R["G"]["tasks"]] == [t["acquired"] for t in C["tasks"]],
        }
        th = {
            "1_retention": m["retention"] >= 0.99,
            "2_plasticity": m["plasticity"] >= 0.9,
            "3_transfer": m["transfer"] >= 0.95,
            "4_no_wrong_qualified": m["wrong_qualified_sealed"] == 0,
            "5_correction": m["correction_propagated"] == m["correction_affected"],
            "6_uncertainty": m["spurious_on_undefined"] == 0 and m["ambiguous_replies"] >= 0.95 * m["ambiguous_queries"],
            "7_scale": m["interactions"] >= 1000 and m["processes"] >= 30,
            "8_controls": m["frozen_phaseB_acquired"] <= 0.1 and m["shuffled_match"] <= 0.1 and m["geometry_disabled_same"],
        }
        allpass = allpass and all(th.values())
        arms = {a: {"acquired": sum(t["acquired"] for t in R[a]["tasks"]),
                    "sealed_correct": sum(t["correct"] for t in R[a]["tasks"]),
                    "sealed_n": sum(t["n_sealed"] for t in R[a]["tasks"]),
                    "task_cpu_s": round(sum(t["cost"]["cpu_s"] for t in R[a]["tasks"]), 3),
                    "evaluations": sum(t["cost"]["evaluations"] for t in R[a]["tasks"]),
                    "row_ops": sum(t["cost"]["row_ops"] for t in R[a]["tasks"]),
                    "library_uses": sum(t["uses_library"] for t in R[a]["tasks"]),
                    "examples_plus_questions": sum(len(t["evidence"]) for t in R[a]["tasks"]),
                    "interactions": R[a]["interactions"], "processes": R[a]["processes"],
                    "final_state_bytes": R[a]["final_state_bytes"]} for a in CLI_ARMS}
        ref = runs[(seed, "R")]
        arms["R"] = {"acquired": sum(t["acquired"] for t in ref), "sealed_correct": sum(t["correct"] for t in ref),
                     "sealed_n": sum(t["n_sealed"] for t in ref), "task_cpu_s": round(sum(t["cpu_s"] for t in ref), 3),
                     "evaluations": sum(t["evaluated"] for t in ref)}
        aB = amort(C, R["B"], overhead)
        aP = amort(C, R["P"], overhead)
        rep["seeds"][seed] = {"metrics": m, "thresholds": th, "arms": arms,
                              "A_vs_empty": aB, "A_reuse_vs_primitive": aP,
                              "H1": aB[-1]["A"] is not None and aB[-1]["A"] > 0,
                              "H2": aP[-1]["A"] is not None and aP[-1]["A"] > 0}
    rep["all_thresholds_pass"] = allpass
    return rep


def main(argv):
    seeds = [11, 22, 33]
    jobs = 8
    for i, a in enumerate(argv):
        if a == "--seeds":
            seeds = [int(x) for x in argv[i + 1].split(",")]
        if a == "--jobs":
            jobs = int(argv[i + 1])
    OUT.mkdir(parents=True, exist_ok=True)
    sha0 = source_hash()
    sealed = set()
    for s in seeds:
        sealed |= sealed_tokens(world(s))
    (ROOT / "benchmarks/sealed_tokens.json").write_text(json.dumps(sorted(sealed)) + "\n")
    trained = ROOT / "data/trained/state.json"
    text = trained.read_text() if trained.exists() else ""
    sealed_ok = not any(f'"{t}"' in text for t in sealed)
    t0 = time.time()
    with Pool(jobs) as pool:
        res = pool.map(run_arm, [(s, a) for s in seeds for a in CLI_ARMS])
    runs = {(r["seed"], r["arm"]): r for r in res}
    for s in seeds:
        runs[(s, "R")] = run_reference(s, runs[(s, "C")])
    sha1 = source_hash()
    rep = evaluate(runs, seeds, sha0, sha1, sealed_ok)
    rep["wall_s"] = round(time.time() - t0, 1)
    (OUT / "g46_raw.json").write_text(json.dumps({f"{k[0]}:{k[1]}": v for k, v in runs.items()}))
    (OUT / "g46_receipt.json").write_text(json.dumps(rep, indent=1))
    for s in seeds:
        x = rep["seeds"][s]
        print(s, json.dumps(x["metrics"]), json.dumps(x["thresholds"]))
        print("  arms", json.dumps({a: (v["acquired"], v["sealed_correct"], v["task_cpu_s"]) for a, v in x["arms"].items()}))
        print("  A_36", x["A_vs_empty"][-1], "A_reuse_36", x["A_reuse_vs_primitive"][-1], "H1", x["H1"], "H2", x["H2"])
    print("all_thresholds_pass", rep["all_thresholds_pass"], "wall", rep["wall_s"])
    return 0 if rep["all_thresholds_pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
