"""G50 part B: the G46 curriculum (base engine) with `complete` statements (docs/G50.md).
Arms: C (as G46), E (C + --answers, PX teacher), K (E + `complete s` for every subject the
teacher answers). Run: python3 benchmarks/g50b.py [--seeds ...] [--out g50b] [--dev]
"""
from __future__ import annotations
import json
import shutil
import subprocess
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT))
import g46  # noqa: E402
import g48  # noqa: E402
from px import g46_th, status_mix  # noqa: E402

ARMS = {"C": [], "E": ["--answers"], "K": ["--answers"]}
SEEDS = [61, 62, 63, 64, 65, 66, 67]


def job(args):
    seed, arm, out = args
    g46.FLAGS.update(ARMS)
    g46.RICH = {"E", "K"}
    g46.COMPLETE = {"K"}
    g46.OUT = Path(out)
    d = g46.OUT / f"seed{seed}"
    d.mkdir(parents=True, exist_ok=True)
    for p in d.glob(f"{arm}.json.archive"):
        shutil.rmtree(p)
    for p in d.glob(f"result_{arm}.json"):
        p.unlink()  # never reuse a cached result
    r = g46.run_arm((seed, arm))
    st = json.loads((d / f"{arm}.json").read_text())["state"]
    r["complete_active"] = len(st.get("complete", {}))
    r["complete_log"] = st.get("complete_log", [])
    return r


def main(argv):
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    seeds = [int(x) for x in argv[argv.index("--seeds") + 1].split(",")] if "--seeds" in argv else SEEDS
    name = "g50b_dev" if "--dev" in argv else (argv[argv.index("--out") + 1] if "--out" in argv else "g50b")
    OUT = ROOT / "artifacts" / name
    OUT.mkdir(parents=True, exist_ok=True)
    sha0 = g48.source_hash()
    with Pool(8) as pool:
        res = pool.map(job, [(s, a, str(OUT)) for s in seeds for a in ARMS])
    R = {(r["seed"], r["arm"]): r for r in res}
    per = {}
    for s in seeds:
        per[s] = {}
        for a in ARMS:
            m, th = g46_th(R[(s, a)])
            t = R[(s, a)]["tasks"]
            per[s][a] = {"metrics": m, "thresholds": th, "acquired": sum(x["acquired"] for x in t),
                         "statuses": status_mix(t), "qualified": sum(x["status"] == "qualified" for x in t),
                         "qualified_acquired": sum(x["status"] == "qualified" and x["acquired"] for x in t),
                         "questions": sum(len(x["asked"]) for x in t),
                         "complete_active": R[(s, a)].get("complete_active"),
                         "complete_retracted": len(R[(s, a)].get("complete_log", [])),
                         "cpu_total_all_s": R[(s, a)].get("cpu_total_all_s")}
    q = {a: sum(per[s][a]["qualified"] for s in seeds) for a in ARMS}
    th = {"KB1_K_wrong_qualified_0": all(per[s]["K"]["metrics"]["wrong_qualified_sealed"] == 0 for s in seeds),
          "KB2_K_qualifies_more_than_E": q["K"] > q["E"],
          "KB3_K_no_harm_1to6": all(per[s]["K"]["thresholds"][k] for s in seeds for k, v in per[s]["E"]["thresholds"].items() if v),
          "source_unchanged": sha0 == g48.source_hash()}
    rep = {"started": started, "head": head, "seeds": seeds, "per_seed": per, "qualified": q, "thresholds": th,
           "all_pass": all(th.values()), "source_sha256": sha0, "engine_sha256": g48.engine_hash(),
           "cpu_total_all_s": {a: round(sum(per[s][a]["cpu_total_all_s"] or 0 for s in seeds), 3) for a in ARMS}}
    (OUT / f"{name}_receipt.json").write_text(json.dumps(rep, indent=1, default=str))
    (OUT / f"{name}_raw.json").write_text(json.dumps({f"{k[0]}:{k[1]}": v for k, v in R.items()}, default=str))
    print(json.dumps({"thresholds": th, "qualified": q, "cpu": rep["cpu_total_all_s"],
                      "per_seed": {s: {a: (v["qualified"], v["acquired"], v["statuses"], v["complete_retracted"],
                                           [k for k, x in v["thresholds"].items() if not x]) for a, v in per[s].items()}
                                   for s in seeds}}, indent=1, default=str))
    return 0 if rep["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
