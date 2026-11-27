"""G47: hierarchical reuse under matched budgets. Protocol: docs/G47.md.
Reuses the G46 world, teacher and sequence; only the arms differ.
Run: python3 benchmarks/g47.py [--seeds 11,22,33]
"""

from __future__ import annotations
import json
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT))
import g46  # noqa: E402

ARMS = {"K": ([], 2), "Q": (["--no-library"], 2), "L": ([], 3), "M": (["--no-library"], 3)}
for a, (f, dp) in ARMS.items():
    g46.FLAGS[a] = f
    g46.DEEPEN[a] = dp
g46.OUT = ROOT / "artifacts/g47"


def summary(r):
    t = r.get("tasks", [])
    fam = r.get("families", [])
    return {"acquired": sum(x["acquired"] for x in t), "tasks": len(t),
            "sealed_correct": sum(x["correct"] for x in t), "sealed_n": sum(x["n_sealed"] for x in t),
            "wrong_qualified": sum(rw["wrong_qualified"] for x in t for rw in x["rows"]),
            "task_cpu_s": round(sum(x["cost"]["cpu_s"] for x in t), 3),
            "evaluations": sum(x["cost"]["evaluations"] for x in t), "row_ops": sum(x["cost"]["row_ops"] for x in t),
            "executions": sum(x["cost"]["executions"] for x in t),
            "maintenance_cpu_s": round(sum(f.get("cost", {}).get("cpu_s", 0) for f in fam), 3),
            "library_uses": sum(x["uses_library"] for x in t),
            "questions": sum(len(x["asked"]) for x in t), "final_state_bytes": r.get("final_state_bytes"),
            "acquired_by_shape": {sh: sum(x["acquired"] for x in t if x["shape"] == sh)
                                  for sh in sorted({x["shape"] for x in t})}}


def main(argv):
    seeds = [11, 22, 33]
    if "--seeds" in argv:
        seeds = [int(x) for x in argv[argv.index("--seeds") + 1].split(",")]
    g46.OUT.mkdir(parents=True, exist_ok=True)
    sha0 = g46.source_hash()
    with Pool(8) as pool:
        res = pool.map(g46.run_arm, [(s, a) for s in seeds for a in ARMS])
    runs = {(r["seed"], r["arm"]): r for r in res}
    rep = {"engine_sha256": sha0, "unchanged": sha0 == g46.source_hash(), "seeds": {}}
    for s in seeds:
        S = {a: summary(runs[(s, a)]) for a in ARMS}
        rep["seeds"][s] = {"arms": S,
                           "H3_lib_reach_d2": S["K"]["acquired"] >= 1.5 * max(S["Q"]["acquired"], 1),
                           "H5_lib_cost_d3_per_acquired": round(S["L"]["task_cpu_s"] / max(S["L"]["acquired"], 1), 4),
                           "H5_prim_cost_d3_per_acquired": round(S["M"]["task_cpu_s"] / max(S["M"]["acquired"], 1), 4)}
    (g46.OUT / "g47_receipt.json").write_text(json.dumps(rep, indent=1))
    (g46.OUT / "g47_raw.json").write_text(json.dumps({f"{k[0]}:{k[1]}": v for k, v in runs.items()}))
    for s in seeds:
        print(s, json.dumps({a: (v["acquired"], v["sealed_correct"], v["wrong_qualified"], v["task_cpu_s"], v["evaluations"])
                             for a, v in rep["seeds"][s]["arms"].items()}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
