"""PX: teacher statements `-> !none` / `-> !several` (docs/PX.md, registered before the run).
Part A: G48 worlds, arms P (standard teacher), R (--answers, extended teacher), V (R + adaptive retention).
Part B: G46 curriculum, arms C (as G46) and E (C + --answers, extended teacher).
Run: python3 benchmarks/px.py [--a-seeds ...] [--b-seeds ...] [--out px] [--dev]
"""

from __future__ import annotations
import json
import shutil
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT))
import g46  # noqa: E402
import g48  # noqa: E402

A_ARMS = {"P": ["--programs"], "R": ["--programs", "--answers"], "V": ["--programs", "--answers", "--adaptive-retention"]}
B_ARMS = {"C": [], "E": ["--answers"]}
A_SEEDS = [521, 522, 523, 524, 525, 526, 527]
B_SEEDS = [11, 22, 33, 44, 55]
SEED33_TASK = (33, "bbtwyr")  # the registered G46 threshold-6 failure (docs/G46_SEED33.md)


def job_a(args):
    seed, arm, out = args
    g48.ARMS.update(A_ARMS)
    g48.RICH = {"R", "V"}
    g48.ABSTAIN = True
    g48.OUT = Path(out)
    return g48.run_arm((seed, arm, 2))


def job_b(args):
    seed, arm, out = args
    g46.FLAGS.update(B_ARMS)
    g46.RICH = {"E"}
    g46.OUT = Path(out)
    d = g46.OUT / f"seed{seed}"
    d.mkdir(parents=True, exist_ok=True)
    for p in d.glob(f"{arm}.json.archive"):
        shutil.rmtree(p)
    return g46.run_arm((seed, arm))


def g46_th(run):
    """G46 thresholds 1-6, computed from one arm's run exactly as g46.evaluate does for C."""
    fams, t = run["families"], run["tasks"]
    rows = [r for x in t for r in x["rows"]]
    amb = [r for r in rows if r["truth"][0] == "amb"]
    corr = [f["correction"] for f in fams if "correction" in f]
    m = {"retention": round(sum(f["retention"]["unchanged"] for f in fams) / max(sum(f["retention"]["n"] for f in fams), 1), 4),
         "plasticity": round(sum(x["acquired"] for x in t) / len(t), 4),
         "transfer": round(sum(f["transfer"]["correct"] for f in fams) / max(sum(f["transfer"]["n"] for f in fams), 1), 4),
         "wrong_qualified_sealed": sum(r["wrong_qualified"] for r in rows),
         "correction_affected": sum(c["affected"] for c in corr), "correction_propagated": sum(c["propagated"] for c in corr),
         "spurious_on_undefined": sum(r["spurious"] for r in rows),
         "ambiguous_queries": len(amb), "ambiguous_replies": sum(r["ok"] for r in amb)}
    th = {"1_retention": m["retention"] >= 0.99, "2_plasticity": m["plasticity"] >= 0.9, "3_transfer": m["transfer"] >= 0.95,
          "4_no_wrong_qualified": m["wrong_qualified_sealed"] == 0,
          "5_correction": m["correction_propagated"] == m["correction_affected"],
          "6_uncertainty": m["spurious_on_undefined"] == 0 and m["ambiguous_replies"] >= 0.95 * m["ambiguous_queries"]}
    return m, th


def status_mix(tasks, key="status"):
    out = {}
    for x in tasks:
        st = x.get(key) or "none"
        out[st] = out.get(st, 0) + 1
    return out


def main(argv):
    get = lambda flag, d: [int(x) for x in argv[argv.index(flag) + 1].split(",")] if flag in argv else d  # noqa: E731
    a_seeds, b_seeds = get("--a-seeds", A_SEEDS), get("--b-seeds", B_SEEDS)
    name = argv[argv.index("--out") + 1] if "--out" in argv else "px"
    OUT = ROOT / "artifacts" / name
    (OUT / "a").mkdir(parents=True, exist_ok=True)
    (OUT / "b").mkdir(parents=True, exist_ok=True)
    sha0 = g48.source_hash()
    jobs_a = [(s, a, str(OUT / "a")) for s in a_seeds for a in A_ARMS]
    jobs_b = [(s, a, str(OUT / "b")) for s in b_seeds for a in B_ARMS]
    with Pool(8) as pool:
        ra = pool.map(job_a, jobs_a)
        rb = pool.map(job_b, jobs_b)
    A = {(r["seed"], r["arm"]): r for r in ra}
    B = {(r["seed"], r["arm"]): r for r in rb}
    rep = {"source_sha256": sha0, "engine_sha256": g48.engine_hash(), "a_seeds": a_seeds, "b_seeds": b_seeds}
    # Part A
    ma = {}
    for arm in A_ARMS:
        ts = [t for s in a_seeds for t in A[(s, arm)]["tasks"]]
        neg = sum(t.get("negative_statements", 0) for t in ts)
        ma[arm] = {"by_class": {c: dict(zip(("accuracy", "n"), g48.acc([t for t in ts if t["class"] == c])))
                                for c in ("T1", "T2", "T3", "T4")},
                   "T1_depth_ge3": dict(zip(("accuracy", "n"), g48.acc([t for t in ts if t["class"] == "T1"], lambda r: r["depth"] >= 3))),
                   "wrong_qualified": sum(r["wrong_qualified"] for t in ts for r in t["rows"]),
                   "status": {c: status_mix([t for t in ts if t["class"] == c]) for c in ("T1", "T2", "T3", "T4")},
                   "questions": sum(len(t["asked"]) for t in ts),
                   "negative_statements": neg,
                   "abstain": {c: {"n": sum(t["abstain"]["n"] for t in ts if t["class"] == c),
                                   "spurious": sum(t["abstain"]["spurious"] for t in ts if t["class"] == c)}
                               for c in ("T1", "T2", "T3", "T4")},
                   "abstain_all": {"n": sum(t["abstain"]["n"] for t in ts), "spurious": sum(t["abstain"]["spurious"] for t in ts)},
                   "cpu_total_s": round(sum(A[(s, arm)]["cpu_total_s"] for s in a_seeds), 3)}
    R_ = ma["R"]
    sp = lambda a: ma[a]["abstain_all"]["spurious"] / max(ma[a]["abstain_all"]["n"], 1)  # noqa: E731
    thA = {"PXA1_R_wrong_qualified_0": R_["wrong_qualified"] == 0,
           "PXA2_V_identical_to_R": all(A[(s, "V")]["replies_sha"] == A[(s, "R")]["replies_sha"] for s in a_seeds),
           "PXA3_R_fewer_spurious_than_P": sp("R") < sp("P")}
    ma["spurious_rate"] = {a: round(sp(a), 4) for a in A_ARMS}
    rep["A"] = {"metrics": ma, "thresholds": thA}
    # Part B
    mb, thB = {}, {}
    for s in b_seeds:
        mb[s] = {}
        for arm in B_ARMS:
            m, th = g46_th(B[(s, arm)])
            t = B[(s, arm)]["tasks"]
            mb[s][arm] = {"metrics": m, "thresholds": th, "acquired": sum(x["acquired"] for x in t),
                          "statuses": status_mix(t, "status"), "questions": sum(len(x["asked"]) for x in t),
                          "negative_statements": sum(1 for x in t for e in x["evidence"] if str(e[1]).startswith("!")),
                          "cpu_total_all_s": B[(s, arm)].get("cpu_total_all_s")}
    s33, tname = SEED33_TASK
    if s33 in b_seeds:
        for arm in B_ARMS:
            task = [x for x in B[(s33, arm)]["tasks"] if x["name"] == tname]
            rep[f"seed33_task_{arm}"] = {k: task[0].get(k) for k in ("status", "seq", "acquired", "asked", "evidence", "correct", "n_sealed")} if task else None
        thB["PXB1_E_seed33_threshold6"] = mb[s33]["E"]["thresholds"]["6_uncertainty"]
    thB["PXB2_E_no_harm_1to6"] = all(mb[s]["E"]["thresholds"][k] for s in b_seeds for k, v in mb[s]["C"]["thresholds"].items() if v)
    thB["PXB2_E_wrong_qualified_0"] = all(mb[s]["E"]["metrics"]["wrong_qualified_sealed"] == 0 for s in b_seeds)
    rep["B"] = {"per_seed": mb, "thresholds": thB}
    rep["source_unchanged"] = sha0 == g48.source_hash()
    rep["all_pass"] = all(thA.values()) and all(thB.values()) and rep["source_unchanged"]
    fn = f"{name}_dev" if "--dev" in argv else name
    (OUT / f"{fn}_receipt.json").write_text(json.dumps(rep, indent=1, default=str))
    (OUT / f"{fn}_raw.json").write_text(json.dumps({"A": {f"{k[0]}:{k[1]}": v for k, v in A.items()},
                                                    "B": {f"{k[0]}:{k[1]}": v for k, v in B.items()}}, default=str))
    print(json.dumps({"A": thA, "B": thB, "A_status": {a: ma[a]["status"] for a in A_ARMS},
                      "A_acc": {a: (ma[a]["by_class"], ma[a]["T1_depth_ge3"], ma[a]["abstain"]) for a in A_ARMS},
                      "spurious_rate": ma["spurious_rate"],
                      "B_summary": {s: {a: (v["acquired"], v["statuses"], v["negative_statements"], v["thresholds"]["6_uncertainty"])
                                        for a, v in mb[s].items()} for s in b_seeds}, "all_pass": rep["all_pass"]}, indent=1, default=str))
    return 0 if rep["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
