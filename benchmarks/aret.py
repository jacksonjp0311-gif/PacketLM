"""ARET: evidence-gated adaptive retention vs static retention (docs/ARET.md).

Same teacher, worlds, seeds, budgets and cost accounting as G46 / G46-U. Arms on one frozen engine:
  C  static retention (everything hot)        A  adaptive retention (--adaptive-retention)
  B  empty state per task (reference for the utility problem)
Writes artifacts/aret/{g46,g46u}/ and artifacts/aret/aret_receipt.json.
Run: python3 benchmarks/aret.py [--seeds 11,22,33]
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
import g46u  # noqa: E402

ARMS = ["C", "A", "B"]
OUT = ROOT / "artifacts/aret"
WORLDS = {"g46": g46.world, "g46u": g46u.world_unrelated}


def run_one(args):
    curriculum, seed, arm = args
    g46.FLAGS["A"] = ["--adaptive-retention"]
    g46.world = WORLDS[curriculum]
    g46.OUT = OUT / curriculum
    d = g46.OUT / f"seed{seed}"
    d.mkdir(parents=True, exist_ok=True)
    done = d / f"result_{arm}.json"
    if not (done.exists() and json.loads(done.read_text()).get("engine_sha256") == g46.source_hash()):
        for p in d.glob(f"{arm}.json.archive"):
            shutil.rmtree(p)  # benchmark scratch from an earlier run of this arm, never the engine's own archive
    r = g46.run_arm((seed, arm))
    arch = d / f"{arm}.json.archive"
    r["archive_bytes"] = sum(p.stat().st_size for p in arch.glob("*.json")) if arch.exists() else 0
    r["archive_files"] = len(list(arch.glob("*.json"))) if arch.exists() else 0
    r["curriculum"] = curriculum
    return r


def rows_of(run):
    return [(t["acquired"], t["correct"], tuple(r["norm"] or "" for r in t["rows"])) for t in run["tasks"]]


def fam_view(run):
    return [{k: f.get(k) for k in ("correction", "transfer", "retention", "post_correction_unchanged")}
            for f in run["families"]]


def summary(run):
    t = run["tasks"]
    return {"acquired": sum(x["acquired"] for x in t), "sealed_correct": sum(x["correct"] for x in t),
            "task_cpu_s": round(sum(x["cost"]["cpu_s"] for x in t), 3),
            "maintenance_cpu_s": round(sum(f.get("cost", {}).get("cpu_s", 0) for f in run["families"]), 3),
            "processes": run["processes"], "final_hot_bytes": run["final_state_bytes"],
            "archive_bytes": run.get("archive_bytes"), "archive_files": run.get("archive_files"),
            "hot_bytes_by_task": [x["state_bytes"] for x in t]}


def main(argv):
    seeds = [11, 22, 33]
    if "--seeds" in argv:
        seeds = [int(x) for x in argv[argv.index("--seeds") + 1].split(",")]
    OUT.mkdir(parents=True, exist_ok=True)
    sha0 = g46.source_hash()
    jobs = [(c, s, a) for c in WORLDS for s in seeds for a in ARMS]
    with Pool(6) as pool:
        res = pool.map(run_one, jobs)
    runs = {(r["curriculum"], r["seed"], r["arm"]): r for r in res}
    rep = {"engine_sha256": sha0, "unchanged": sha0 == g46.source_hash(), "curricula": {}}
    for c in WORLDS:
        rep["curricula"][c] = {}
        for s in seeds:
            C, A, B = (runs[(c, s, a)] for a in ARMS)
            rep["curricula"][c][s] = {
                "arms": {a: summary(runs[(c, s, a)]) for a in ARMS},
                "no_harm_tasks": rows_of(A) == rows_of(C),
                "no_harm_families": fam_view(A) == fam_view(C),
                "wrong_qualified_A": sum(r["wrong_qualified"] for t in A["tasks"] for r in t["rows"]),
                "aborted": [a for a in ARMS if runs[(c, s, a)].get("aborted")],
            }
    rep["H_R1_no_harm"] = all(v["no_harm_tasks"] and v["no_harm_families"] and v["wrong_qualified_A"] == 0
                              and not v["aborted"] for c in rep["curricula"].values() for v in c.values())
    (OUT / "aret_receipt.json").write_text(json.dumps(rep, indent=1))
    for c in WORLDS:
        (OUT / f"{c}_raw.json").write_text(json.dumps(
            {f"{s}:{a}": runs[(c, s, a)] for s in seeds for a in ARMS}))
    print(json.dumps({c: {s: {"no_harm": (v["no_harm_tasks"], v["no_harm_families"]),
                              "cpu": {a: v["arms"][a]["task_cpu_s"] for a in ARMS},
                              "maint": {a: v["arms"][a]["maintenance_cpu_s"] for a in ARMS},
                              "hot": {a: v["arms"][a]["final_hot_bytes"] for a in ARMS},
                              "archive": v["arms"]["A"]["archive_bytes"]}
                          for s, v in rep["curricula"][c].items()} for c in WORLDS}, indent=1))
    print("H_R1_no_harm", rep["H_R1_no_harm"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
