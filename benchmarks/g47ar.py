"""G47-AR: G47 with adaptive retention on (docs/G47_AR.md, registered before the run).
Arms K, Q, L, M exactly as G47; W = K + --adaptive-retention; Y = L + --adaptive-retention.
Primary cost: whole-run, whole-process CPU (cpu_total_s summed over every call, maintenance and
startup included). Run: python3 benchmarks/g47ar.py [--seeds 11,22,33,44,55]
"""

from __future__ import annotations
import hashlib
import json
import shutil
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT))
import g46  # noqa: E402

ARMS = {"K": ([], 2), "Q": (["--no-library"], 2), "L": ([], 3), "M": (["--no-library"], 3),
        "W": (["--adaptive-retention"], 2), "Y": (["--adaptive-retention"], 3)}
PAIRS = {"W": "K", "Y": "L"}
OUT = ROOT / "artifacts/g47ar"
SEEDS = [11, 22, 33, 44, 55]


def run_one(job):
    seed, arm = job
    for a, (f, dp) in ARMS.items():
        g46.FLAGS[a] = f
        g46.DEEPEN[a] = dp
    g46.OUT = OUT
    d = OUT / f"seed{seed}"
    d.mkdir(parents=True, exist_ok=True)
    done = d / f"result_{arm}.json"
    if not (done.exists() and json.loads(done.read_text()).get("engine_sha256") == g46.source_hash()):
        for p in d.glob(f"{arm}.json.archive"):
            shutil.rmtree(p)  # benchmark scratch of an earlier run of this arm
    r = g46.run_arm((seed, arm))
    arch = d / f"{arm}.json.archive"
    r["archive_files"] = len(list(arch.glob("*.json"))) if arch.exists() else 0
    return r


def view(run):
    """Everything the learner said, per task and family (H-AR1 compares these)."""
    t = [(x["acquired"], x["correct"], tuple(r["norm"] or "" for r in x["rows"])) for x in run["tasks"]]
    f = [{k: v.get(k) for k in ("correction", "transfer", "retention", "post_correction_unchanged")} for v in run["families"]]
    return hashlib.sha256(json.dumps([t, f], sort_keys=True, default=str).encode()).hexdigest()


def summary(r):
    t = r.get("tasks", [])
    return {"acquired": sum(x["acquired"] for x in t), "tasks": len(t),
            "sealed_correct": sum(x["correct"] for x in t), "sealed_n": sum(x["n_sealed"] for x in t),
            "wrong_qualified": sum(rw["wrong_qualified"] for x in t for rw in x["rows"]),
            "cpu_total_all_s": r.get("cpu_total_all_s"), "cpu_all_s": r.get("cpu_all_s"),
            "task_cpu_s": round(sum(x["cost"]["cpu_s"] for x in t), 3),
            "processes": r.get("processes"), "final_state_bytes": r.get("final_state_bytes"),
            "archive_files": r.get("archive_files", 0), "aborted": r.get("aborted"), "view": view(r) if t else None}


def main(argv):
    seeds = SEEDS
    if "--seeds" in argv:
        seeds = [int(x) for x in argv[argv.index("--seeds") + 1].split(",")]
    OUT.mkdir(parents=True, exist_ok=True)
    sha0 = g46.source_hash()
    with Pool(8) as pool:
        res = pool.map(run_one, [(s, a) for s in seeds for a in ARMS])
    runs = {(r["seed"], r["arm"]): r for r in res}
    S = {s: {a: summary(runs[(s, a)]) for a in ARMS} for s in seeds}
    ar1 = all(S[s][a]["view"] == S[s][b]["view"] for s in seeds for a, b in PAIRS.items())
    lower = {a: sum(S[s][a]["cpu_total_all_s"] < S[s][b]["cpu_total_all_s"] for s in seeds) for a, b in PAIRS.items()}
    need = len(seeds) - 1
    rep = {"engine_sha256": sha0, "unchanged": sha0 == g46.source_hash(), "seeds": seeds, "per_seed": S,
           "H_AR1_no_harm": ar1,
           "H_AR2_lower_total_cpu": {a: {"seeds_lower": lower[a], "need": need, "pass": lower[a] >= need} for a in PAIRS},
           "ratios_total_cpu": {a: [round(S[s][a]["cpu_total_all_s"] / S[s][b]["cpu_total_all_s"], 4) for s in seeds]
                                for a, b in PAIRS.items()},
           "G47_H3_lib_reach_d2": {s: S[s]["K"]["acquired"] >= 1.5 * max(S[s]["Q"]["acquired"], 1) for s in seeds},
           "G47_H5_total_cpu_per_acquired_d3": {s: {a: round(S[s][a]["cpu_total_all_s"] / max(S[s][a]["acquired"], 1), 4)
                                                     for a in ("L", "Y", "M")} for s in seeds}}
    (OUT / "g47ar_receipt.json").write_text(json.dumps(rep, indent=1))
    (OUT / "g47ar_raw.json").write_text(json.dumps({f"{k[0]}:{k[1]}": v for k, v in runs.items()}))
    print(json.dumps({k: rep[k] for k in ("H_AR1_no_harm", "H_AR2_lower_total_cpu", "ratios_total_cpu",
                                         "G47_H3_lib_reach_d2", "G47_H5_total_cpu_per_acquired_d3", "unchanged")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
