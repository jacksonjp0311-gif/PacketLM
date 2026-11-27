"""Verifier: recompute the G58 library-scaling statistics and the registered stop rule / flatness
decision from the per-run files in docs/evidence/g58/libscale (independent bootstrap copy)."""
import json, random, sys, glob, os
D = sys.argv[1] if len(sys.argv) > 1 else "docs/evidence/g58/libscale"
R = {}
for f in glob.glob(os.path.join(D, "s*_L*_*.json")):
    r = json.load(open(f)); R[(r["seed"], r["L"], r["arm"])] = r
seeds = sorted({k[0] for k in R}); sizes = sorted({k[1] for k in R}); arms = ["j0", "j", "r"]
def boot(v, reps=5000, seed=0):
    g = random.Random(seed); n = len(v)
    m = sorted(sum(g.choice(v) for _ in range(n)) / n for _ in range(reps))
    return [round(sum(v) / n, 4), [round(m[int(0.025 * reps)], 4), round(m[int(0.975 * reps) - 1], 4)]]
out = {"runs": len(R), "seeds": seeds, "sizes": sizes}
for a in arms:
    s = out[a] = {}
    s["mean_task_ms"] = {L: round(1000 * sum(R[(x, L, a)]["mean_task_cpu_s"] for x in seeds) / len(seeds), 3) for L in sizes}
    s["snap_ms"] = {L: round(1000 * sum(R[(x, L, a)]["snapshot_cpu_s"] for x in seeds) / len(seeds), 3) for L in sizes}
    s["R64_1024"] = boot([R[(x, 1024, a)]["mean_task_cpu_s"] / R[(x, 64, a)]["mean_task_cpu_s"] for x in seeds])
    s["R0_1024"] = boot([R[(x, 1024, a)]["mean_task_cpu_s"] / R[(x, 0, a)]["mean_task_cpu_s"] for x in seeds])
    s["R64_amort_1024"] = boot([R[(x, 1024, a)]["amort_task_cpu_s"] / R[(x, 64, a)]["amort_task_cpu_s"] for x in seeds])
    # amortized form recomputed from its parts (journaled calls / tasks / 64 * snapshot)
    am = lambda x, L: R[(x, L, a)]["mean_task_cpu_s"] + R[(x, L, a)]["journaled_calls"] / 10 / 64 * R[(x, L, a)]["snapshot_cpu_s"]
    s["R64_amort_1024_from_parts"] = boot([am(x, 1024) / am(x, 64) for x in seeds])
    s["journaled_calls"] = sorted({R[(x, L, a)]["journaled_calls"] for x in seeds for L in sizes})
g = lambda a, k: out[a][k]
out["threshold_L64"] = g("j0", "R64_1024")[0] / 2; out["threshold_L0"] = g("j0", "R0_1024")[0] / 2
out["material_vs_L64"] = g("r", "R64_1024")[1][1] <= out["threshold_L64"]
out["material_vs_L0"] = g("r", "R0_1024")[1][1] <= out["threshold_L0"]
out["material"] = out["material_vs_L64"] and out["material_vs_L0"]
out["flat"] = g("r", "R64_1024")[1][1] <= 1.25
# report-only: the stop rule charged with snapshots (amortized form, both sides)
out["material_amort_vs_L64"] = g("r", "R64_amort_1024")[1][1] <= g("j0", "R64_amort_1024")[0] / 2
out["guards"] = {
    "replies_eq_j0": all(R[(x, L, a)]["reply_stream_sha256"] == R[(x, L, "j0")]["reply_stream_sha256"] for x in seeds for L in sizes for a in arms),
    "state_eq_j0": all(R[(x, L, a)]["state_sha256"] == R[(x, L, "j0")]["state_sha256"] for x in seeds for L in sizes for a in arms),
    "known_const": all(R[(x, L, a)]["known"] == R[(x, 0, a)]["known"] for x in seeds for L in sizes for a in arms),
    "no_snap_in_window": not any(r["snapshot_in_window"] for r in R.values())}
rc = json.load(open(os.path.join(D, "g58_libscale_receipt.json")))
out["matches_receipt"] = all(rc["summary"][a][k] == out[a][k] for a in arms for k in ("R64_1024", "R0_1024", "R64_amort_1024")) \
    and all(rc[k] == out[k] for k in ("material_vs_L64", "material_vs_L0", "material")) and rc["flat_r"] == out["flat"]
print(json.dumps(out, indent=1, default=str))
