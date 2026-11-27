"""G59: the learning-amortization qualification gate (docs/G59.md, registered before the run).

The G58 long-lived protocol (benchmarks/g58.py: G50 `complete` teacher, whole-process CPU with
maintenance, instrument 70297af, flags --answers --bounded --lean; B and P add --no-library; every
arm under `python -m packetlm.serve`; B starts every task from a new, empty state path), on fresh
seeds, five curricula (benchmarks/g59_worlds.py):
  comp     g46.world (36 tasks)                      C, B, P, F
  comprep  g46.world on an independent seed set      C, B, P, F
  unrel    g46u.world_unrelated (24 tasks)           C, B, P
  mixed    comp families each followed by 2 unrelated families (48 tasks)   C, B, P
  long     comp's phase pattern x4 (144 tasks)       C, B, P
Two engine configurations per role:
  Xr  G58 (--indexed --incremental --routed)
  Xk  G59 (+ --partitioned)
Guards: every Xk reply stream equals its Xr twin's and every Xk final state file is byte-identical
to its Xr twin's; 0 wrong-qualified sealed answers in every C arm; instrument pinned and unmodified.
Each finished arm run is written to disk at once (<out>/<cur>/<arm>/seed<seed>/job.json, progress.jsonl).
Run: python3 benchmarks/g59.py [--out g59] [--seeds-comp ...] [--only comp,unrel]
"""
from __future__ import annotations
import hashlib
import json
import os
import subprocess
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT))
import g46  # noqa: E402
import g46u  # noqa: E402
import g48  # noqa: E402
import g56  # noqa: E402
import g58  # noqa: E402
import g59_analysis as G  # noqa: E402
from g59_worlds import world_long, world_mixed  # noqa: E402
from la_export import export  # noqa: E402
from px import g46_th  # noqa: E402
from g51 import instrument, INSTRUMENT, PIN  # noqa: E402

CURRICULA = {"comp": (g46.world, ["C", "B", "P", "F"]), "comprep": (g46.world, ["C", "B", "P", "F"]),
             "unrel": (g46u.world_unrelated, ["C", "B", "P"]), "mixed": (world_mixed, ["C", "B", "P"]),
             "long": (world_long, ["C", "B", "P"])}
g56.CURRICULA.update(CURRICULA)  # g56.job builds each arm's world from this table
SEEDS = {"comp": [301, 302, 303, 304, 305, 306, 307], "comprep": [311, 312, 313, 314, 315, 316, 317],
         "unrel": [321, 322, 323, 324, 325, 326, 327], "mixed": [331, 332, 333, 334, 335, 336, 337],
         "long": [341, 342, 343, 344, 345, 346, 347]}
g58.PROTO.update({"k": ["--indexed", "--incremental", "--routed", "--partitioned"]})
PROTOS = "rk"
HARNESS = ["benchmarks/g59.py", "benchmarks/g59_analysis.py", "benchmarks/g59_worlds.py", "benchmarks/g59_registered.sh",
           "benchmarks/g58.py", "benchmarks/g57b.py", "benchmarks/g57.py", "benchmarks/g56.py", "benchmarks/g46.py",
           "benchmarks/g46u.py", "benchmarks/g51.py", "benchmarks/la_export.py", "benchmarks/px.py"]
# registered thresholds (docs/G59.md §6): G58's L3r penalty, halved
L3_G58 = -1.898
Q3_FLOOR = L3_G58 / 2


def job(args):
    cur, seed, arm, out = args
    r = g58.job((cur, seed, arm, out))
    r["curriculum"] = cur
    return r


def summarize(raw, seeds, arms, roles):
    per = {}
    for s in seeds:
        per[s] = {}
        for a in arms:
            rr = raw[f"{s}:{a}"]
            t = rr["tasks"]
            m, th = g46_th(rr) if a[0] != "B" else (None, None)
            per[s][a] = {"tasks": len(t), "solved": sum(x["correct"] == x["n_sealed"] for x in t),
                         "sealed_correct": sum(x["correct"] for x in t), "sealed_n": sum(x["n_sealed"] for x in t),
                         "qualified": sum(x["status"] == "qualified" for x in t),
                         "status": {k: sum(str(x["status"]) == k for x in t) for k in sorted({str(x["status"]) for x in t})},
                         "censored": sum(x["status"] is None for x in t),
                         "uses_library": sum(x["uses_library"] for x in t),
                         "wrong_qualified_sealed": sum(r["wrong_qualified"] for x in t for r in x["rows"]),
                         "transfer_wrong_qualified": sum(f.get("transfer", {}).get("wrong_qualified", 0) for f in rr["families"]),
                         "retention_changed": sum(f["retention"]["n"] - f["retention"]["unchanged"] for f in rr["families"] if "retention" in f),
                         "cpu_total_all_s": rr.get("cpu_total_all_s"), "g46_thresholds": th,
                         "reply_stream_sha256": rr["reply_stream_sha256"], "final_state_sha256": rr["final_state_sha256"],
                         "calls": rr["processes"]}
    outcomes = {a: {k: sum(per[s][a][k] for s in seeds) for k in ("tasks", "solved", "sealed_correct", "sealed_n", "qualified",
                                                                   "censored", "uses_library", "wrong_qualified_sealed",
                                                                   "transfer_wrong_qualified", "retention_changed")}
                for a in arms}
    exact = {r: all(per[s][r + "k"]["reply_stream_sha256"] == per[s][r + "r"]["reply_stream_sha256"]
                    and per[s][r + "k"]["final_state_sha256"] == per[s][r + "r"]["final_state_sha256"] for s in seeds) for r in roles}
    return per, outcomes, exact


def analyses(raw, seeds, roles, csvs, n):
    """Every registered analysis of one curriculum (docs/G59.md §6)."""
    primary = [("Ck+maint", "Bk"), ("Ck+maint", "Pk+maint"), ("Ck+maint", "Cr+maint")]
    secondary = [("Ck", "Bk"), ("Ck", "Pk"), ("Cr+maint", "Br"), ("Bk", "Br"), ("Pk+maint", "Pr+maint")]
    if "F" in roles:
        secondary += [("Fk+maint", "Fr+maint"), ("Ck+maint", "Fk+maint")]
    out = {"primary": [instrument(csvs["cpu_total_s"], a, b, n) for a, b in primary],
           "secondary": [instrument(csvs["cpu_total_s"], a, b, n) for a, b in secondary],
           # secondary resources (registered, not primary): evaluations and teacher lines, same instrument
           "resources": {res: [instrument(csvs[res], a, b, n) for a, b in [("Ck+maint", "Bk"), ("Ck+maint", "Pk+maint")]]
                         for res in ("evaluations", "lines")}}
    out["parsed"] = {f"{x['cont']}||{x['base']}": G.parse(x["report"]) for x in out["primary"] + out["secondary"]}
    out["parsed_resources"] = {res: {f"{x['cont']}||{x['base']}": G.parse(x["report"]) for x in v} for res, v in out["resources"].items()}
    out["work_split"] = {w: {"vs_B": G.work_split(raw, seeds, "Ck+maint", "Bk", w), "vs_P": G.work_split(raw, seeds, "Ck+maint", "Pk+maint", w)}
                         for w in ("evaluations", "executions", "row_ops")}
    out["strata_B_depth"] = G.strata(raw, seeds, "Ck", "Bk")
    out["censoring"] = G.censoring(raw, seeds, "Ck", "Bk")
    out["rate_ratio"] = G.rate_ratio(raw, seeds, "Ck", "Bk")
    out["in_run"] = G.in_run(raw, seeds, "Ck", "Bk")
    out["emergence"] = {"reuse": G.reuse(raw, seeds, "Ck"), "depth": {"Ck": G.depth_hist(raw, seeds, "Ck"), "Bk": G.depth_hist(raw, seeds, "Bk")},
                        "cascades": G.cascades(raw, seeds, "Ck"), "retention": G.retention(raw, seeds, "Ck"),
                        "lines_C/B": round(sum(G.totals(raw, seeds, "Ck+maint", "lines")) / sum(G.totals(raw, seeds, "Bk", "lines")), 4),
                        "lines_C/B_tasks_only": round(sum(G.totals(raw, seeds, "Ck", "lines")) / sum(G.totals(raw, seeds, "Bk", "lines")), 4)}
    if "P" in roles:
        for w in ("evaluations", "executions"):
            out["emergence"][f"{w}_C/P"] = round(sum(G.totals(raw, seeds, "Ck+maint", w)) / sum(G.totals(raw, seeds, "Pk+maint", w)), 4)
    return out


def gate(q):
    """Registered qualification (docs/G59.md §6): PASS iff Q1-Q4 all hold, else HOLD."""
    P = lambda c, k: q[c]["analyses"]["parsed"][k]["A"]  # noqa: E731
    out = {}
    out["Q1_comp_positive"] = P("comp", "Ck+maint||Bk")[1][0] > 0
    corr = {}
    for c, v in q.items():
        o = v["outcomes"]
        corr[c] = {"wrong_qualified_0": o["Ck"]["wrong_qualified_sealed"] == 0 and o["Ck"]["transfer_wrong_qualified"] == 0,
                   "retention_changed_0": o["Ck"]["retention_changed"] == 0,
                   "sealed_correct_C_ge_B": o["Ck"]["sealed_correct"] >= o["Bk"]["sealed_correct"]}
    out["Q2_detail"] = corr
    out["Q2_no_correctness_or_retention_loss"] = all(all(x.values()) for x in corr.values())
    out["Q3_unrel_penalty_halved"] = P("unrel", "Ck+maint||Bk")[1][0] > Q3_FLOOR
    out["Q4a_comp_replicates"] = P("comprep", "Ck+maint||Bk")[1][0] > 0
    out["Q4b_mixed_positive"] = P("mixed", "Ck+maint||Bk")[1][0] > 0
    out["PASS"] = all(out[k] for k in ("Q1_comp_positive", "Q2_no_correctness_or_retention_loss", "Q3_unrel_penalty_halved",
                                        "Q4a_comp_replicates", "Q4b_mixed_positive"))
    out["verdict"] = "PASS" if out["PASS"] else "HOLD"
    out["switch_rule_triggered"] = not out["PASS"]  # docs/G59.md §8 (James, 08:26)
    # per search-depth stratum (docs/G59.md §6c): qualified positive iff the lower CI > 0; deepest-first
    # holds iff, in comp, the deepest stratum has the highest point A (and, if any stratum qualifies,
    # the deepest is among those that do)
    st = {c: q[c]["analyses"]["strata_B_depth"] for c in q if c != "unrel"}
    out["strata_qualified"] = {c: {k: v["A"][1][0] > 0 for k, v in d.items()} for c, d in st.items()}
    cs = st["comp"]
    deep = max(cs, key=int)
    anyq = [k for k, v in out["strata_qualified"]["comp"].items() if v]
    out["deepest_first_comp"] = all(cs[deep]["A"][0] >= v["A"][0] for v in cs.values()) and (not anyq or deep in anyq)
    L = q["long"]["analyses"]["parsed"]["Ck||Bk"]
    a, b = L["A"], L["beta"]
    out["accumulation"] = {"A_final_task_only": a, "beta": b,
                           "crosses_zero": a[1][0] > 0,
                           "plateau_below_zero": a[1][1] < 0 and b[1][0] <= 0 <= b[1][1],
                           "diverging_below_zero": a[1][1] < 0 and b[1][1] < 0,
                           "rate_ratio": q["long"]["analyses"]["rate_ratio"]}
    return out


def main(argv):
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()  # noqa: E731
    head, dirty = git("rev-parse", "HEAD"), git("status", "--porcelain")
    harness = hashlib.sha256(b"".join((ROOT / f).read_bytes() for f in HARNESS)).hexdigest()
    pin = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=INSTRUMENT, capture_output=True, text=True).stdout.strip()
    idirty = subprocess.run(["git", "status", "--porcelain"], cwd=INSTRUMENT, capture_output=True, text=True).stdout.strip()
    only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else list(CURRICULA)
    seeds = {c: ([int(x) for x in argv[argv.index(f"--seeds-{c}") + 1].split(",")] if f"--seeds-{c}" in argv else SEEDS[c]) for c in only}
    name = argv[argv.index("--out") + 1] if "--out" in argv else "g59"
    OUT = ROOT / "artifacts" / name
    OUT.mkdir(parents=True, exist_ok=True)
    sha0 = g48.source_hash()
    LOCK = Path("/workspace/REGISTERED_RUN.lock")
    lock0 = LOCK.read_text().strip() if LOCK.exists() else None
    load0 = os.getloadavg()
    arms = {c: [r + p for r in CURRICULA[c][1] for p in PROTOS] for c in only}
    jobs = [(c, s, a, str(OUT)) for c in only for s in seeds[c] for a in arms[c]]
    jobs.sort(key=lambda j: (j[0] != "long", j[2][0] not in ("C", "P")))  # long jobs first
    res = []
    with Pool(int(os.environ.get("G59_WORKERS", "4"))) as pool:
        for r in pool.imap_unordered(job, jobs):
            res.append(r)
            with open(OUT / "progress.jsonl", "a") as fh:
                fh.write(json.dumps({"curriculum": r["curriculum"], "seed": r["seed"], "arm": r["arm"],
                                     "cpu_total_all_s": r.get("cpu_total_all_s"), "reply_stream_sha256": r["reply_stream_sha256"],
                                     "final_state_sha256": r["final_state_sha256"], "at": time.strftime("%H:%M:%S")}) + "\n")
    runs = {(r["curriculum"], r["seed"], r["arm"]): r for r in res}
    rep = {"started": started, "finished": None, "head": head, "git_status_porcelain": dirty, "harness_sha256": harness,
           "instrument": {"path": str(INSTRUMENT), "head": pin, "pinned": pin == PIN, "unmodified": idirty == ""},
           "seeds": seeds, "source_sha256": sha0, "engine_sha256": g48.engine_hash(), "curricula": {}}
    for c in only:
        roles = CURRICULA[c][1]
        raw = {f"{s}:{a}": {**runs[(c, s, a)], "arm": a} for s in seeds[c] for a in arms[c]}
        (OUT / f"{c}_raw.json").write_text(json.dumps(raw, default=str))
        csvs = {}
        for res_ in ("cpu_total_s", "evaluations", "lines"):
            csvs[res_] = OUT / f"{c}_{res_}.csv"
            (export(raw, csvs[res_], None, res_) if res_ == "cpu_total_s" else G.export_resource(raw, csvs[res_], res_))
        n = len(runs[(c, seeds[c][0], "Ck")]["tasks"])
        per, outcomes, exact = summarize(raw, seeds[c], arms[c], roles)
        rep["curricula"][c] = {"n": n, "per_seed": per, "outcomes": outcomes, "exact_k_equals_r": exact,
                               "cpu_total": {a: round(sum(per[s][a]["cpu_total_all_s"] for s in seeds[c]), 3) for a in arms[c]},
                               "analyses": analyses(raw, seeds[c], roles, csvs, n)}
    q = rep["curricula"]
    rep["guards"] = {"exact_replies_and_state_k_equal_r": all(all(v["exact_k_equals_r"].values()) for v in q.values()),
                     "no_wrong_qualified_C": all(v["outcomes"][a]["wrong_qualified_sealed"] == 0 for v in q.values() for a in ("Cr", "Ck")),
                     "instrument_pinned_unmodified": rep["instrument"]["pinned"] and rep["instrument"]["unmodified"],
                     "all_reports_ran": all(x["rc"] == 0 for v in q.values() for x in v["analyses"]["primary"] + v["analyses"]["secondary"]),
                     "source_unchanged": sha0 == g48.source_hash()}
    if set(CURRICULA) <= set(only):
        rep["gate"] = gate(q)
    rep["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    rep["lock"] = {"start": lock0, "end": LOCK.read_text().strip() if LOCK.exists() else None}
    rep["loadavg"] = {"start": load0, "end": os.getloadavg()}
    (OUT / f"{name}_receipt.json").write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps({"guards": rep["guards"], "gate": rep.get("gate"),
                      **{c: {"primary": [(x["cont"], x["base"], x["report"].splitlines()[0] if x["report"] else x["err"]) for x in v["analyses"]["primary"]],
                             "outcomes": v["outcomes"], "exact": v["exact_k_equals_r"]} for c, v in q.items()}}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
