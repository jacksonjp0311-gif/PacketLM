"""G60H: the HDC prototype on the G59 gate protocol (docs/G60H.md, registered before the run).

The G59 gate protocol unchanged (benchmarks/g59.py: G58 long-lived serve protocol, G50 `complete`
teacher with PX statements, whole-process CPU with maintenance, curricula comp/comprep/unrel/mixed/long
from benchmarks/g59_worlds.py, instrument 70297af) with the engine process replaced by the HDC engine
(`python -m packetlm.hdc.serve`). Roles C (learner), B (empty state per task, --no-library), P
(--no-library, long-lived); one configuration h. Arms Ch, Bh, Ph.
Run: python3 benchmarks/g60h.py [--out g60h] [--seeds-comp ...] [--only comp,unrel]
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
import g56  # noqa: E402
import g59  # noqa: E402
import g59_analysis as G  # noqa: E402
from g59_worlds import world_long, world_mixed  # noqa: E402
from la_export import export  # noqa: E402
from g51 import instrument, INSTRUMENT, PIN  # noqa: E402

CURRICULA = {"comp": (g46.world, ["C", "B", "P"]), "comprep": (g46.world, ["C", "B", "P"]),
             "unrel": (g46u.world_unrelated, ["C", "B", "P"]), "mixed": (world_mixed, ["C", "B", "P"]),
             "long": (world_long, ["C", "B", "P"])}
g56.CURRICULA.update(CURRICULA)
# fresh seeds (docs/G60H.md §5); dev seeds are 9xx
SEEDS = {"comp": [401, 402, 403, 404, 405, 406, 407], "comprep": [411, 412, 413, 414, 415, 416, 417],
         "unrel": [421, 422, 423, 424, 425, 426, 427], "mixed": [431, 432, 433, 434, 435, 436, 437],
         "long": [441, 442, 443, 444, 445, 446, 447]}
HARNESS = ["benchmarks/g60h.py", "benchmarks/g59.py", "benchmarks/g59_analysis.py", "benchmarks/g59_worlds.py",
           "benchmarks/g56.py", "benchmarks/g46.py", "benchmarks/g46u.py", "benchmarks/g51.py", "benchmarks/la_export.py",
           "benchmarks/px.py"]
ENGINE = ["packetlm/hdc/__init__.py", "packetlm/hdc/codes.py", "packetlm/hdc/engine.py", "packetlm/hdc/serve.py"]
Q3_FLOOR = g59.Q3_FLOOR  # registered in G59 (half of G58's L3r), kept for comparability
G59_COMP_CK = {"sealed_correct": 252, "solved": None}  # G59 docs §12: Ck sealed correct on comp (252 of 7 seeds)


class HServer(g56.Server):
    def __init__(self):
        import subprocess as sp
        self.p = sp.Popen([sys.executable, "-m", "packetlm.hdc.serve"], cwd=ROOT, stdin=sp.PIPE,
                          stdout=sp.PIPE, stderr=sp.PIPE, text=True, bufsize=1)


def engine_hash():
    return hashlib.sha256(b"".join((ROOT / f).read_bytes() for f in ENGINE)).hexdigest()


def job(args):
    cur, seed, arm, out = args
    role = arm[0]
    import shutil
    g56.Server = HServer
    saved = dict(g56.BASEF)
    root = Path(out) / "_h"
    try:
        r = g56.job((cur, seed, role + "s", str(root)))
    finally:
        g56.BASEF.clear()
        g56.BASEF.update(saved)
    src = root / cur / (role + "s") / f"seed{seed}"
    dst = Path(out) / cur / arm / f"seed{seed}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    src.rename(dst)
    st = dst / f"{role}.json"
    r["arm"], r["proto"], r["curriculum"] = arm, "h", cur
    r["final_state_sha256"] = hashlib.sha256(st.read_bytes()).hexdigest() if st.exists() else None
    # HDC counters (cumulative per server process; the last call's values)
    last = None
    for t in r["tasks"]:
        last = t
    (dst / "job.json").write_text(json.dumps(r, default=str))
    return r


def hdc_counters(out, cur, seeds, arm):
    """Decode counters read from the arm's journal-free logs: the cumulative counters of the last call
    are not kept by g46, so they are recomputed from the per-call stats stored in job.json if present."""
    return None


def analyses(raw, seeds, csvs, n):
    primary = [("Ch+maint", "Bh"), ("Ch+maint", "Ph+maint")]
    # decomposition (docs/G60H.md §6c, verifier M1 of 80cfb17): state carriage without a library (P||B),
    # library use (C||P), the total (C||B), each with and without maintenance, and maintenance alone
    secondary = [("Ch", "Bh"), ("Ch", "Ph"), ("Ph", "Bh"), ("Ph+maint", "Bh"), ("Ch+maint", "Ch"), ("Ph+maint", "Ph")]
    out = {"primary": [instrument(csvs["cpu_total_s"], a, b, n) for a, b in primary],
           "secondary": [instrument(csvs["cpu_total_s"], a, b, n) for a, b in secondary],
           "resources": {res: [instrument(csvs[res], a, b, n) for a, b in [("Ch+maint", "Bh"), ("Ch+maint", "Ph+maint")]]
                         for res in ("evaluations", "lines")}}
    out["parsed"] = {f"{x['cont']}||{x['base']}": G.parse(x["report"]) for x in out["primary"] + out["secondary"]}
    out["parsed_resources"] = {res: {f"{x['cont']}||{x['base']}": G.parse(x["report"]) for x in v} for res, v in out["resources"].items()}
    out["work_split"] = {w: {"vs_B": G.work_split(raw, seeds, "Ch+maint", "Bh", w), "vs_P": G.work_split(raw, seeds, "Ch+maint", "Ph+maint", w)}
                         for w in ("evaluations", "executions", "row_ops")}
    out["maintenance_share"] = {a: round(sum(sum(f.get("cost", {}).get("cpu_total_s", 0) for f in raw[f"{s_}:{a}"]["families"]) for s_ in seeds)
                                         / sum(raw[f"{s_}:{a}"]["cpu_total_all_s"] for s_ in seeds), 4) for a in ("Ch", "Ph")}
    out["strata_B_depth"] = G.strata(raw, seeds, "Ch", "Bh")
    out["censoring"] = G.censoring(raw, seeds, "Ch", "Bh")
    out["rate_ratio"] = G.rate_ratio(raw, seeds, "Ch", "Bh")
    out["in_run"] = G.in_run(raw, seeds, "Ch", "Bh")
    out["emergence"] = {"reuse": G.reuse(raw, seeds, "Ch"), "depth": {"Ch": G.depth_hist(raw, seeds, "Ch"), "Bh": G.depth_hist(raw, seeds, "Bh")},
                        "cascades": G.cascades(raw, seeds, "Ch"), "retention": G.retention(raw, seeds, "Ch"),
                        "lines_C/B": round(sum(G.totals(raw, seeds, "Ch+maint", "lines")) / sum(G.totals(raw, seeds, "Bh", "lines")), 4)}
    return out


def gate(q):
    """Registered qualification (docs/G60H.md §6): the G59 gate on the HDC arms."""
    P = lambda c, k: q[c]["analyses"]["parsed"][k]["A"]  # noqa: E731
    out = {"Q1_comp_positive": P("comp", "Ch+maint||Bh")[1][0] > 0}
    corr = {}
    for c, v in q.items():
        o = v["outcomes"]
        corr[c] = {"wrong_qualified_0": o["Ch"]["wrong_qualified_sealed"] == 0 and o["Ch"]["transfer_wrong_qualified"] == 0,
                   "retention_changed_0": o["Ch"]["retention_changed"] == 0,
                   "sealed_correct_C_ge_B": o["Ch"]["sealed_correct"] >= o["Bh"]["sealed_correct"]}
    out["Q2_detail"] = corr
    out["Q2_no_correctness_or_retention_loss"] = all(all(x.values()) for x in corr.values())
    out["Q3_unrel_penalty_halved"] = P("unrel", "Ch+maint||Bh")[1][0] > Q3_FLOOR
    out["Q4a_comp_replicates"] = P("comprep", "Ch+maint||Bh")[1][0] > 0
    out["Q4b_mixed_positive"] = P("mixed", "Ch+maint||Bh")[1][0] > 0
    out["PASS"] = all(out[k] for k in ("Q1_comp_positive", "Q2_no_correctness_or_retention_loss", "Q3_unrel_penalty_halved",
                                        "Q4a_comp_replicates", "Q4b_mixed_positive"))
    out["verdict"] = "PASS" if out["PASS"] else "HOLD"
    st = {c: q[c]["analyses"]["strata_B_depth"] for c in q if c != "unrel"}
    out["strata_qualified"] = {c: {k: v["A"][1][0] > 0 for k, v in d.items()} for c, d in st.items()}
    cs = st["comp"]
    deep = max(cs, key=int)
    anyq = [k for k, v in out["strata_qualified"]["comp"].items() if v]
    out["deepest_first_comp"] = all(cs[deep]["A"][0] >= v["A"][0] for v in cs.values()) and (not anyq or deep in anyq)
    L = q["long"]["analyses"]["parsed"]["Ch||Bh"]
    a, b = L["A"], L["beta"]
    out["accumulation"] = {"A_final_task_only": a, "beta": b, "crosses_zero": a[1][0] > 0,
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
    name = argv[argv.index("--out") + 1] if "--out" in argv else "g60h"
    margin = int(argv[argv.index("--margin") + 1]) if "--margin" in argv else 1  # docs/G60H.md §6: 1 primary, 2 robustness
    for r_ in g56.BASEF:
        g56.BASEF[r_] = g56.BASEF[r_] + [f"--margin={margin}"]
    OUT = ROOT / "artifacts" / name
    OUT.mkdir(parents=True, exist_ok=True)
    sha0 = engine_hash()
    LOCK = Path("/workspace/REGISTERED_RUN.lock")
    lock0 = LOCK.read_text().strip() if LOCK.exists() else None
    load0 = os.getloadavg()
    arms = {c: [r + "h" for r in CURRICULA[c][1]] for c in only}
    jobs = [(c, s, a, str(OUT)) for c in only for s in seeds[c] for a in arms[c]]
    jobs.sort(key=lambda j: (j[0] != "long", j[2][0] not in ("C", "P")))
    res = []
    with Pool(int(os.environ.get("G60H_WORKERS", "4"))) as pool:
        for r in pool.imap_unordered(job, jobs):
            res.append(r)
            with open(OUT / "progress.jsonl", "a") as fh:
                fh.write(json.dumps({"curriculum": r["curriculum"], "seed": r["seed"], "arm": r["arm"],
                                     "cpu_total_all_s": r.get("cpu_total_all_s"), "at": time.strftime("%H:%M:%S")}) + "\n")
    runs = {(r["curriculum"], r["seed"], r["arm"]): r for r in res}
    rep = {"started": started, "head": head, "git_status_porcelain": dirty, "harness_sha256": harness,
           "instrument": {"path": str(INSTRUMENT), "head": pin, "pinned": pin == PIN, "unmodified": idirty == ""},
           "seeds": seeds, "engine_sha256": sha0, "margin": margin, "curricula": {}}
    for c in only:
        raw = {f"{s}:{a}": {**runs[(c, s, a)], "arm": a} for s in seeds[c] for a in arms[c]}
        (OUT / f"{c}_raw.json").write_text(json.dumps(raw, default=str))
        csvs = {}
        for res_ in ("cpu_total_s", "evaluations", "lines"):
            csvs[res_] = OUT / f"{c}_{res_}.csv"
            (export(raw, csvs[res_], None, res_) if res_ == "cpu_total_s" else G.export_resource(raw, csvs[res_], res_))
        n = len(runs[(c, seeds[c][0], "Ch")]["tasks"])
        per, outcomes, _ = g59.summarize(raw, seeds[c], arms[c], [])
        rep["curricula"][c] = {"n": n, "per_seed": per, "outcomes": outcomes,
                               "cpu_total": {a: round(sum(per[s][a]["cpu_total_all_s"] for s in seeds[c]), 3) for a in arms[c]},
                               "analyses": analyses(raw, seeds[c], csvs, n)}
    q = rep["curricula"]
    rep["guards"] = {"no_wrong_qualified_C": all(v["outcomes"]["Ch"]["wrong_qualified_sealed"] == 0 for v in q.values()),
                     "instrument_pinned_unmodified": rep["instrument"]["pinned"] and rep["instrument"]["unmodified"],
                     "all_reports_ran": all(x["rc"] == 0 for v in q.values() for x in v["analyses"]["primary"] + v["analyses"]["secondary"]),
                     "source_unchanged": sha0 == engine_hash()}
    if set(CURRICULA) <= set(only):
        rep["gate"] = gate(q)
    rep["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    rep["lock"] = {"start": lock0, "end": LOCK.read_text().strip() if LOCK.exists() else None}
    rep["loadavg"] = {"start": load0, "end": os.getloadavg()}
    (OUT / f"{name}_receipt.json").write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps({"guards": rep["guards"], "gate": rep.get("gate"),
                      **{c: {"primary": [(x["cont"], x["base"], x["report"].splitlines()[0] if x["report"] else x["err"]) for x in v["analyses"]["primary"]],
                             "outcomes": v["outcomes"]} for c, v in q.items()}}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
