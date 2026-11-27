"""Verifier (report-only): the library-scaling stop rule charged with snapshots, from the registered
per-run files. Form A = the harness's amortized form (journaled/tasks/64 x snapshot CPU). Form B adds
the duplicate period ix_check (Low 3 of verify-8994490, still present: the K = 64 full validation and
the snapshot fall in the same call, each running ix_check), estimated per run as snapshot CPU x the
ix_check share measured by snap_profile.py at L = 1024 (j0 7.1/67.1, j 243.6/300.2, r 257.9/311.5)."""
import json, glob, random
R = {}
for f in glob.glob("docs/evidence/g58/libscale/s*_L*_*.json"):
    x = json.load(open(f)); R[(x["seed"], x["L"], x["arm"])] = x
seeds = sorted({k[0] for k in R})
share = {"j0": 7.1 / 67.1, "j": 243.6 / 300.2, "r": 257.9 / 311.5}
def boot(v, reps=5000, seed=0):
    g = random.Random(seed); n = len(v); m = sorted(sum(g.choice(v) for _ in range(n)) / n for _ in range(reps))
    return [round(sum(v) / n, 3), [round(m[int(.025 * reps)], 3), round(m[int(.975 * reps) - 1], 3)]]
def cost(s, L, a, form):
    x = R[(s, L, a)]; per = x["journaled_calls"] / 10 / 64
    return x["mean_task_cpu_s"] + per * x["snapshot_cpu_s"] * (1 if form == "A" else 1 + share[a])
out = {}
for form in ("A", "B"):
    for base in (64, 0):
        st = {a: boot([cost(s, 1024, a, form) / cost(s, base, a, form) for s in seeds]) for a in ("j0", "j", "r")}
        out[f"{form}_R{base}_1024"] = st
        out[f"{form}_R{base}_material"] = st["r"][1][1] <= st["j0"][0] / 2
        out[f"{form}_R{base}_flat"] = st["r"][1][1] <= 1.25
    out[f"{form}_task_ms_L1024"] = {a: round(1000 * sum(cost(s, 1024, a, form) for s in seeds) / len(seeds), 2) for a in ("j0", "j", "r")}
print(json.dumps(out, indent=1))
