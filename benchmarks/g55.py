"""G55: option 3, an observation-independent guard budget under `complete` (docs/G55.md, registered
before the run). G49 harness (programs mode, exact scan, `complete` teacher), arms differing only in
the closed-world guard budget `--closed-guards=N` (default N = MAX_GUARDS = 8, the G52 rule):
  F8   F teacher, N = 8 (G52 engine rule; reference)
  F32  F teacher, N = 32 (covers the 25-28-pair components; the 63-65-pair ones stay capped)
  L32  lying teacher (G49 L) at N = 32: withheld facts while `complete` is stated, revealed later
(N = 24 and 72 were dropped after an aborted dev run, docs/G55.md §4.)
Run: python3 benchmarks/g55.py [--seeds ...] [--out g55] [--dev]
"""
from __future__ import annotations
import hashlib
import json
import subprocess
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT))
import g48  # noqa: E402
import g49  # noqa: E402
from packetlm.g45_test import source_hash  # noqa: E402

BASE = ["--programs", "--answers"]
ARMS = {"F8": BASE, "F32": BASE + ["--closed-guards=32"], "L32": BASE + ["--closed-guards=32"]}
SEEDS = [561, 562, 563, 564, 565, 566, 567]
g49.ARMS = ARMS
g49.RICH = set(ARMS)
g49.COMPLETE = set(ARMS)
g49.WITHHOLD = {"L32"}
HARNESS = ["benchmarks/g55.py", "benchmarks/g49.py", "benchmarks/g48.py", "packetlm/g45_test.py"]


def main(argv):
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()  # noqa: E731
    head, dirty = git("rev-parse", "HEAD"), git("status", "--porcelain")
    harness = hashlib.sha256(b"".join((ROOT / f).read_bytes() for f in HARNESS)).hexdigest()
    seeds = [int(x) for x in argv[argv.index("--seeds") + 1].split(",")] if "--seeds" in argv else SEEDS
    name = "g55_dev" if "--dev" in argv else (argv[argv.index("--out") + 1] if "--out" in argv else "g55")
    out = ROOT / "artifacts" / name
    out.mkdir(parents=True, exist_ok=True)
    sha0 = source_hash()
    jobs = [(s, a, 2) for s in seeds for a in ARMS]
    with Pool(8, initializer=g49._set_out, initargs=(str(out),)) as pool:
        res = pool.map(g49.run_arm, jobs)
    runs = {(r["seed"], r["arm"]): r for r in res}
    g = lambda a: [t for s in seeds for t in runs[(s, a)]["tasks"]]  # noqa: E731
    m = {a: g49.metrics(g(a)) for a in ARMS}
    for a in ARMS:
        m[a]["cpu_total_s"] = round(sum(runs[(s, a)]["cpu_total_s"] for s in seeds), 3)
        m[a]["cpu_total_per_seed"] = [runs[(s, a)]["cpu_total_s"] for s in seeds]
        m[a]["scan_complete"] = sum(m[a]["scans"])
        m[a]["guard_gap_tasks"] = sum(1 for t in g(a) if (t["hyp"].get("scan") or {}).get("guard_gap", 0) > 0)
        m[a]["tasks"] = len(g(a))
    ratio = {a: sorted(runs[(s, a)]["cpu_total_s"] / runs[(s, "F8")]["cpu_total_s"] for s in seeds) for a in ("F32",)}
    med = {a: v[len(v) // 2] for a, v in ratio.items()}
    L = g("L32")
    false_said = sum(len(t["complete_false"]) for t in L)
    retracted = sum(any(e["x"] == x for e in t["complete_log"]) for t in L for x in t["complete_false"])
    rules = {}
    for a in ("F32",):
        q = m[a]["qualified_tasks"] > m["F8"]["qualified_tasks"] and m[a]["wrong_qualified"] == 0
        c = med[a] <= 2.0
        rules[a] = {"Q_more_qualified_0_wrong": q, "C_median_cost_ratio_le_2": c, "adoptable": q and c,
                    "median_cost_ratio": round(med[a], 3)}
    guards = {"F8_F32_wrong_qualified_0": all(m[a]["wrong_qualified"] == 0 for a in ("F8", "F32")),
              "L32_false_statements_retracted": false_said > 0 and retracted == false_said,
              "L32_wrong_qualified_after_reveal_0": m["L32"]["wrong_qualified"] == 0,
              "source_unchanged": sha0 == source_hash()}
    rep = {"started": started, "head": head, "git_status_porcelain": dirty, "harness_sha256": harness,
           "seeds": seeds, "metrics": m, "rules": rules, "guards": guards, "cost_ratio_per_seed": ratio,
           "lying": {"false_statements": false_said, "retracted": retracted},
           "source_sha256": sha0, "engine_sha256": g48.engine_hash()}
    (out / f"{name}_receipt.json").write_text(json.dumps(rep, indent=1))
    (out / f"{name}_raw.json").write_text(json.dumps({f"{k[0]}:{k[1]}": v for k, v in runs.items()}))
    print(json.dumps({"rules": rules, "guards": guards, "lying": rep["lying"],
                      "summary": {a: {k: m[a][k] for k in ("qualified_tasks", "qualified_by_class", "wrong_qualified",
                                                          "scan_complete", "guard_gap_tasks", "tasks", "by_class",
                                                          "T1_depth_ge4", "cpu_total_s")} for a in ARMS}}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
