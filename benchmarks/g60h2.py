"""G60H2: the equal-check rule on the G59/G60H gate protocol (docs/G60H2.md, registered before the run).

Configurations (arm = role + letter; roles C learner, B empty state per task, P long-lived no library):
  e  equal check (primary): every role uses the base-language certificate (B's rule, margin m, meet in the
     middle, `--certifier=mitm`); C's library only proposes (`--check=equal`).
  p  plain ablation of e (`--plain`): the same engine with exact dicts/sets for every hypervector part.
  o  own-language rule (G60H's): C `--check=own`; used on the decoy curriculum only.
  d  e with the reference DP certifier (`--certifier=dp`); used for the exactness differential only.
The protocol, teacher, instrument and analyses are G60H's (benchmarks/g60h.py), arm names parameterized.
In-run counters (cum_*) are recorded by the harness for every arm run (verifier L3).
Run: python3 benchmarks/g60h2.py --out NAME --config e [--margin 1] [--only comp,...] [--seeds-comp ...]
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
import g56  # noqa: E402
import g59  # noqa: E402
import g59_analysis as G  # noqa: E402
import g60h  # noqa: E402
from g60h2_decoy import world_decoy  # noqa: E402
from la_export import export  # noqa: E402
from g51 import instrument, INSTRUMENT, PIN  # noqa: E402

CURRICULA = dict(g60h.CURRICULA, decoy=(world_decoy, ["C", "B", "P"]))
g56.CURRICULA.update(CURRICULA)
GATE_CURRICULA = ["comp", "comprep", "unrel", "mixed", "long"]
# fresh seeds (docs/G60H2.md §5): never used before (G60H 401-457, dev 9xx, G59 and earlier 1xx-3xx)
SEEDS = {"comp": [501, 502, 503, 504, 505, 506, 507], "comprep": [511, 512, 513, 514, 515, 516, 517],
         "unrel": [521, 522, 523, 524, 525, 526, 527], "mixed": [531, 532, 533, 534, 535, 536, 537],
         "long": [541, 542, 543, 544, 545, 546, 547], "decoy": [561, 562, 563, 564, 565, 566, 567]}
CONFIG = {"e": {"C": ["--check=equal", "--certifier=mitm"], "B": ["--certifier=mitm"], "P": ["--certifier=mitm"]},
          "p": {"C": ["--check=equal", "--certifier=mitm", "--plain"], "B": ["--certifier=mitm", "--plain"],
                "P": ["--certifier=mitm", "--plain"]},
          "o": {"C": ["--check=own", "--certifier=mitm"], "B": ["--certifier=mitm"], "P": ["--certifier=mitm"]},
          "d": {"C": ["--check=equal", "--certifier=dp"], "B": ["--certifier=dp"], "P": ["--certifier=dp"]}}
HARNESS = g60h.HARNESS + ["benchmarks/g60h2.py", "benchmarks/g60h2_decoy.py"]
ENGINE = g60h.ENGINE + ["packetlm/hdc/plain.py"]
Q3_FLOOR = g59.Q3_FLOOR

_C = {"tot": {}, "last": {}}
_orig_call = g56.ServeTeacher.__call__


def _call(self, *lines):
    r = _orig_call(self, *lines)
    rec = self.log[-1]
    if rec["load"].get("loaded") != "memory":  # a new engine object: its counters start at 0
        for k, v in _C["last"].items():
            _C["tot"][k] = _C["tot"].get(k, 0) + v
        _C["last"] = {}
    _C["last"] = {k: v for k, v in rec["stats"].items() if k.startswith("cum_")}
    return r


g56.ServeTeacher.__call__ = _call


def engine_hash():
    return hashlib.sha256(b"".join((ROOT / f).read_bytes() for f in ENGINE)).hexdigest()


def job(args):
    cur, seed, arm, out, margin = args
    role, cfg = arm[0], arm[1]
    saved = list(g56.BASEF[role])
    g56.BASEF[role] = saved + CONFIG[cfg][role] + [f"--margin={margin}"]
    _C["tot"], _C["last"] = {}, {}
    try:
        r = g60h.job((cur, seed, arm, out))
    finally:
        g56.BASEF[role] = saved
    tot = dict(_C["tot"])
    for k, v in _C["last"].items():
        tot[k] = tot.get(k, 0) + v
    r["hdc_counters"] = tot
    r["flags"] = g56.BASEF[role] + CONFIG[cfg][role] + [f"--margin={margin}"]
    return r


def analyses(raw, seeds, csvs, n, x):
    C_, B_, P_ = "C" + x, "B" + x, "P" + x
    primary = [(C_ + "+maint", B_), (C_ + "+maint", P_ + "+maint")]
    secondary = [(C_, B_), (C_, P_), (P_, B_), (P_ + "+maint", B_), (C_ + "+maint", C_), (P_ + "+maint", P_)]
    out = {"primary": [instrument(csvs["cpu_total_s"], a, b, n) for a, b in primary],
           "secondary": [instrument(csvs["cpu_total_s"], a, b, n) for a, b in secondary],
           "resources": {res: [instrument(csvs[res], a, b, n) for a, b in primary] for res in ("evaluations", "lines")}}
    out["parsed"] = {f"{y['cont']}||{y['base']}": G.parse(y["report"]) for y in out["primary"] + out["secondary"]}
    out["parsed_resources"] = {res: {f"{y['cont']}||{y['base']}": G.parse(y["report"]) for y in v} for res, v in out["resources"].items()}
    out["work_split"] = {w: {"vs_B": G.work_split(raw, seeds, C_ + "+maint", B_, w), "vs_P": G.work_split(raw, seeds, C_ + "+maint", P_ + "+maint", w)}
                         for w in ("evaluations", "executions", "row_ops")}
    out["strata_B_depth"] = G.strata(raw, seeds, C_, B_)
    out["censoring"] = G.censoring(raw, seeds, C_, B_)
    out["rate_ratio"] = G.rate_ratio(raw, seeds, C_, B_)
    out["rate_ratio_per_seed"] = {s: G.rate_ratio(raw, [s], C_, B_) for s in seeds}
    out["emergence"] = {"reuse": G.reuse(raw, seeds, C_), "depth": {C_: G.depth_hist(raw, seeds, C_), B_: G.depth_hist(raw, seeds, B_)}}
    return out


def gate(q, x):
    """Registered qualification (docs/G60H2.md §6 = G60H §6 thresholds), arms of configuration x."""
    C_, B_ = "C" + x, "B" + x
    P = lambda c, k: q[c]["analyses"]["parsed"][k]["A"]  # noqa: E731
    k = f"{C_}+maint||{B_}"
    out = {"Q1_comp_positive": P("comp", k)[1][0] > 0}
    corr = {}
    for c, v in q.items():
        if c not in GATE_CURRICULA:
            continue
        o = v["outcomes"]
        corr[c] = {"wrong_qualified_0": o[C_]["wrong_qualified_sealed"] == 0 and o[C_]["transfer_wrong_qualified"] == 0,
                   "retention_changed_0": o[C_]["retention_changed"] == 0,
                   "sealed_correct_C_ge_B": o[C_]["sealed_correct"] >= o[B_]["sealed_correct"]}
    out["Q2_detail"] = corr
    out["Q2_no_correctness_or_retention_loss"] = all(all(y.values()) for y in corr.values())
    out["Q3_unrel_penalty_halved"] = P("unrel", k)[1][0] > Q3_FLOOR
    out["Q4a_comp_replicates"] = P("comprep", k)[1][0] > 0
    out["Q4b_mixed_positive"] = P("mixed", k)[1][0] > 0
    out["PASS"] = all(out[y] for y in ("Q1_comp_positive", "Q2_no_correctness_or_retention_loss", "Q3_unrel_penalty_halved",
                                        "Q4a_comp_replicates", "Q4b_mixed_positive"))
    out["verdict"] = "PASS" if out["PASS"] else "HOLD"
    out["A"] = {c: P(c, k) for c in GATE_CURRICULA}
    out["library_term"] = {c: P(c, f"{C_}+maint||P{x}+maint") for c in GATE_CURRICULA}
    out["strata_comp"] = {kk: v["A"] for kk, v in q["comp"]["analyses"]["strata_B_depth"].items()}
    L = q["long"]["analyses"]["parsed"][f"{C_}||{B_}"]
    out["accumulation"] = {"A": L["A"], "beta": L["beta"], "rate_ratio": q["long"]["analyses"]["rate_ratio"],
                           "rate_ratio_per_seed": q["long"]["analyses"]["rate_ratio_per_seed"]}
    return out


def main(argv):
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()  # noqa: E731
    head, dirty = git("rev-parse", "HEAD"), git("status", "--porcelain")
    harness = hashlib.sha256(b"".join((ROOT / f).read_bytes() for f in HARNESS)).hexdigest()
    pin = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=INSTRUMENT, capture_output=True, text=True).stdout.strip()
    idirty = subprocess.run(["git", "status", "--porcelain"], cwd=INSTRUMENT, capture_output=True, text=True).stdout.strip()
    x = argv[argv.index("--config") + 1] if "--config" in argv else "e"
    only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else list(GATE_CURRICULA)
    seeds = {c: ([int(s) for s in argv[argv.index(f"--seeds-{c}") + 1].split(",")] if f"--seeds-{c}" in argv else SEEDS[c]) for c in only}
    name = argv[argv.index("--out") + 1] if "--out" in argv else f"g60h2_{x}"
    margin = int(argv[argv.index("--margin") + 1]) if "--margin" in argv else 1
    OUT = ROOT / "artifacts" / name
    OUT.mkdir(parents=True, exist_ok=True)
    sha0 = engine_hash()
    LOCK = Path("/workspace/REGISTERED_RUN.lock")
    lock0 = LOCK.read_text().strip() if LOCK.exists() else None
    load0 = os.getloadavg()
    arms = {c: [r + x for r in CURRICULA[c][1]] for c in only}
    jobs = [(c, s, a, str(OUT), margin) for c in only for s in seeds[c] for a in arms[c]]
    jobs.sort(key=lambda j: (j[0] != "long", j[2][0] not in ("C", "P")))
    res = []
    with Pool(int(os.environ.get("G60H_WORKERS", "4"))) as pool:
        for r in pool.imap_unordered(job, jobs):
            res.append(r)
            with open(OUT / "progress.jsonl", "a") as fh:
                fh.write(json.dumps({"curriculum": r["curriculum"], "seed": r["seed"], "arm": r["arm"],
                                     "cpu_total_all_s": r.get("cpu_total_all_s"), "at": time.strftime("%H:%M:%S")}) + "\n")
    runs = {(r["curriculum"], r["seed"], r["arm"]): r for r in res}
    rep = {"started": started, "head": head, "git_status_porcelain": dirty, "harness_sha256": harness, "config": x,
           "flags": {a: runs[(c, seeds[c][0], a)]["flags"] for c in only for a in arms[c]},
           "instrument": {"path": str(INSTRUMENT), "head": pin, "pinned": pin == PIN, "unmodified": idirty == ""},
           "seeds": seeds, "engine_sha256": sha0, "margin": margin, "curricula": {}}
    for c in only:
        raw = {f"{s}:{a}": {**runs[(c, s, a)], "arm": a} for s in seeds[c] for a in arms[c]}
        (OUT / f"{c}_raw.json").write_text(json.dumps(raw, default=str))
        csvs = {}
        for res_ in ("cpu_total_s", "evaluations", "lines"):
            csvs[res_] = OUT / f"{c}_{res_}.csv"
            (export(raw, csvs[res_], None, res_) if res_ == "cpu_total_s" else G.export_resource(raw, csvs[res_], res_))
        n = len(runs[(c, seeds[c][0], "C" + x)]["tasks"])
        per, outcomes, _ = g59.summarize(raw, seeds[c], arms[c], [])
        counters = {a: {} for a in arms[c]}
        for s in seeds[c]:
            for a in arms[c]:
                for kk, v in runs[(c, s, a)]["hdc_counters"].items():
                    counters[a][kk] = counters[a].get(kk, 0) + v
        rep["curricula"][c] = {"n": n, "per_seed": per, "outcomes": outcomes, "counters": counters,
                               "reply_stream_sha256": {f"{s}:{a}": runs[(c, s, a)]["reply_stream_sha256"] for s in seeds[c] for a in arms[c]},
                               "cpu_total": {a: round(sum(per[s][a]["cpu_total_all_s"] for s in seeds[c]), 3) for a in arms[c]},
                               "analyses": analyses(raw, seeds[c], csvs, n, x)}
    q = rep["curricula"]
    rep["guards"] = {"instrument_pinned_unmodified": rep["instrument"]["pinned"] and rep["instrument"]["unmodified"],
                     "all_reports_ran": all(y["rc"] == 0 for v in q.values() for y in v["analyses"]["primary"] + v["analyses"]["secondary"]),
                     "source_unchanged": sha0 == engine_hash()}
    if set(GATE_CURRICULA) <= set(only):
        rep["gate"] = gate(q, x)
    rep["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    rep["lock"] = {"start": lock0, "end": LOCK.read_text().strip() if LOCK.exists() else None}
    rep["loadavg"] = {"start": load0, "end": os.getloadavg()}
    (OUT / f"{name}_receipt.json").write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps({"guards": rep["guards"], "gate": rep.get("gate"),
                      **{c: {"primary": [(y["cont"], y["base"], y["report"].splitlines()[0] if y["report"] else y["err"]) for y in v["analyses"]["primary"]],
                             "outcomes": {a: {kk: v["outcomes"][a].get(kk) for kk in ("sealed_correct", "wrong_qualified_sealed", "transfer_wrong_qualified", "retention_changed")} for a in v["outcomes"]},
                             "counters": v["counters"]} for c, v in q.items()}}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
