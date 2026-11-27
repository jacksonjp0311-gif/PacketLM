"""Verifier: recompute the G57b stop rule and part S summary from the published per-run files only
(docs/evidence/g57/scale for G57 Xi/Xs, docs/evidence/g57b/scale for G57b), with an independent
copy of the bootstrap (same algorithm/seed as benchmarks/g57_scale.boot). Usage: stoprule_recompute.py [DIR_G57B]"""
import json, random, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]


def boot(vals, reps=5000, seed=0):
    rng = random.Random(seed)
    m = sorted(sum(rng.choice(vals) for _ in vals) / len(vals) for _ in range(reps))
    return round(sum(vals) / len(vals), 4), [round(m[int(0.025 * reps)], 4), round(m[int(0.975 * reps) - 1], 4)]


def load(d, seeds, sizes, arms):
    R = {}
    for s in seeds:
        for n in sizes:
            for a in arms:
                R[(s, n, a)] = json.loads((d / f"s{s}_n{n}_{a}.json").read_text())
    return R


def summ(R, seeds, arms, key="mean_task_cpu_s"):
    out = {}
    for a in arms:
        o = out[a] = {}
        for n in (0, 1000, 4000, 16000):
            o[f"mean_ms_{n}"] = round(1000 * sum(R[(s, n, a)][key] for s in seeds) / len(seeds), 3)
        o["R_16000"] = boot([R[(s, 16000, a)][key] / R[(s, 0, a)][key] for s in seeds])
        o["R1k_16000"] = boot([R[(s, 16000, a)][key] / R[(s, 1000, a)][key] for s in seeds])
        if "amort_task_cpu_s" in R[(seeds[0], 0, a)]:
            o["R1k_amort_16000"] = boot([R[(s, 16000, a)]["amort_task_cpu_s"] / R[(s, 1000, a)]["amort_task_cpu_s"] for s in seeds])
    return out


g57 = summ(load(ROOT / "docs/evidence/g57/scale", range(221, 228), (0, 1000, 4000, 16000), "si"), list(range(221, 228)), "si")
print("G57 published files:", json.dumps(g57))
d = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs/evidence/g57b/scale"
sizes = (0, 1000, 4000, 16000) if (d / "s231_n4000_j.json").exists() else (0, 1000, 16000)
R = load(d, range(231, 238), sizes, "sij")
if 4000 not in sizes:
    for k in list(R):
        R[(k[0], 4000, k[2])] = R[(k[0], 1000, k[2])]  # 4000 not run: placeholder, its mean is not reported
g = summ(R, list(range(231, 238)), "sij")
print(f"G57b files {d}:", json.dumps(g))
xi_r1k = g57["i"]["R1k_16000"][0]
print("stop rule: thresholds", {"R1k_16000_upper<=": round(xi_r1k / 2, 4), "R_16000_upper<=": 91.9 / 2})
print("material:", g["j"]["R1k_16000"][1][1] <= xi_r1k / 2, g["j"]["R_16000"][1][1] <= 91.9 / 2,
      "flat (R1k upper<=1.25):", g["j"]["R1k_16000"][1][1] <= 1.25)
