"""Verifier (verify-80cfb17): part S exponents recomputed from the 105 registered per-run files with my own
code: alpha = ln(mean over seeds of T(N2)/T(N1)) / ln(N2/N1), seed-bootstrap 95% CI (5000, my RNG seed).
Metrics: task (mean_task_cpu_s), charged_prop, charged_fixed, work (work_calls), snapshot; plus task-CPU
per work call (time/work), median-of-tasks variant (robustness to the first-task outlier)."""
import glob, json, math, random, statistics as st
R = {}
for p in glob.glob("docs/evidence/g59/scale/s*_n*_*.json"):
    d = json.load(open(p)); R[(d["seed"], d["n"], d["arm"])] = d
seeds = sorted({k[0] for k in R}); arms = ["r0", "r", "k"]
M = {"task": lambda d: d["mean_task_cpu_s"], "charged_prop": lambda d: d["charged_prop_cpu_s"], "charged_fixed": lambda d: d["charged_fixed_cpu_s"],
     "work": lambda d: d["work_calls"], "snapshot": lambda d: d["snapshot_cpu_s"], "task_median": lambda d: st.median(d["task_cpu_s"]),
     "task_drop_first": lambda d: sum(d["task_cpu_s"][1:]) / (len(d["task_cpu_s"]) - 1), "cpu_per_call": lambda d: d["mean_task_cpu_s"] / d["work_calls"]}
def alpha(arm, m, n1, n2, reps=5000):
    r = [M[m](R[(s, n2, arm)]) / M[m](R[(s, n1, arm)]) for s in seeds]
    L = math.log(n2 / n1); rng = random.Random(777)
    bs = sorted(math.log(sum(r[rng.randrange(len(r))] for _ in r) / len(r)) / L for _ in range(reps))
    return round(math.log(sum(r) / len(r)) / L, 3), [round(bs[int(.025 * reps)], 3), round(bs[int(.975 * reps) - 1], 3)], round(sum(r) / len(r), 3)
out = {"seeds": seeds, "runs": len(R)}
for arm in arms:
    out[arm] = {"mean_task_ms": {n: round(1000 * st.mean(R[(s, n, arm)]["mean_task_cpu_s"] for s in seeds), 2) for n in (0, 1000, 16000, 32000, 64000)}}
    for m in M:
        out[arm][m] = {f"{a}-{b}": alpha(arm, m, a, b) for a, b in ((16000, 32000), (16000, 64000), (32000, 64000))}
# guards
out["replies_equal_r0"] = all(R[(s, n, a)]["reply_stream_sha256"] == R[(s, n, "r0")]["reply_stream_sha256"] for s in seeds for n in (0, 1000, 16000, 32000, 64000) for a in ("r", "k"))
out["state_equal_r0"] = all(R[(s, n, a)]["state_sha256"] == R[(s, n, "r0")]["state_sha256"] for s in seeds for n in (0, 1000, 16000, 32000, 64000) for a in ("r", "k"))
out["no_snapshot_in_window"] = not any(d["snapshot_in_window"] for d in R.values())
rk = [R[(s, 64000, "k")]["mean_task_cpu_s"] / R[(s, 16000, "k")]["mean_task_cpu_s"] for s in seeds]
r0 = [R[(s, 64000, "r0")]["mean_task_cpu_s"] / R[(s, 16000, "r0")]["mean_task_cpu_s"] for s in seeds]
out["material"] = {"k_ratio_mean": round(st.mean(rk), 3), "r0_ratio_mean": round(st.mean(r0), 3)}
print(json.dumps(out, indent=1))
