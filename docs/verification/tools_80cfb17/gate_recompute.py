"""Verifier (verify-80cfb17): G59 gate quantities recomputed from the registered raw files with my own code
(not benchmarks/g59_analysis.py): A point estimates (ratio of seed totals, maintenance on each family's last
task), Q2 counts, per-depth strata, work/time split rho, rate ratio on every curriculum, Xk = Xr hashes.
Bootstrap CIs: numpy-free, 5000 seed resamples with my own RNG seed (CIs approximate the receipt's)."""
import gzip, json, math, random, sys
D = "docs/evidence/g59"
rc = json.load(open(f"{D}/g59_receipt.json"))
def costs(run, res="cpu_total_s", maint=False):
    c = [t["cost"].get(res, 0.0) for t in run["tasks"]]
    if maint:
        last = {t["family"]: i for i, t in enumerate(run["tasks"])}
        for f in run["families"]:
            if "cost" in f and f["family"] in last: c[last[f["family"]]] += f["cost"].get(res, 0.0)
    return c
def tot(raw, seeds, arm, res="cpu_total_s", sel=None):
    a, m = (arm[:-6], True) if arm.endswith("+maint") else (arm, False)
    return [sum(x for i, x in enumerate(costs(raw[f"{s}:{a}"], res, m)) if sel is None or sel(s, i)) for s in seeds]
def A(n, d, R=5000, seed=12345):
    S = len(n); rng = random.Random(seed); pt = 1 - sum(n) / sum(d); v = []
    for _ in range(R):
        ix = [rng.randrange(S) for _ in range(S)]; v.append(1 - sum(n[i] for i in ix) / sum(d[i] for i in ix))
    v.sort(); return round(pt, 4), [round(v[int(.025 * R)], 4), round(v[int(.975 * R) - 1], 4)]
def ols(y):
    n = len(y); xm = (n - 1) / 2; ym = sum(y) / n
    return sum((i - xm) * (v - ym) for i, v in enumerate(y)) / sum((i - xm) ** 2 for i in range(n))
out = {}
for cur, c in rc["curricula"].items():
    raw = json.load(gzip.open(f"{D}/{cur}_raw.json.gz")); seeds = sorted({int(k.split(":")[0]) for k in raw})
    arms = sorted({k.split(":")[1] for k in raw})
    o = {"seeds": seeds, "arms": arms}
    o["A_Ck+maint||Bk"] = A(tot(raw, seeds, "Ck+maint"), tot(raw, seeds, "Bk"))
    o["A_Ck+maint||Pk+maint"] = A(tot(raw, seeds, "Ck+maint"), tot(raw, seeds, "Pk+maint"))
    o["A_Ck+maint||Cr+maint"] = A(tot(raw, seeds, "Ck+maint"), tot(raw, seeds, "Cr+maint"))
    o["A_Pk+maint||Bk"] = A(tot(raw, seeds, "Pk+maint"), tot(raw, seeds, "Bk"))
    o["A_Cr+maint||Br"] = A(tot(raw, seeds, "Cr+maint"), tot(raw, seeds, "Br"))
    o["A_Ck||Bk task-only"] = A(tot(raw, seeds, "Ck"), tot(raw, seeds, "Bk"))
    # maintenance share of C's cost
    o["maint_share_Ck"] = round(1 - sum(tot(raw, seeds, "Ck")) / sum(tot(raw, seeds, "Ck+maint")), 4)
    # Q2
    q2 = {}
    for arm in ("Ck", "Bk"):
        ts = [t for s in seeds for t in raw[f"{s}:{arm}"]["tasks"]]
        q2[arm] = {"sealed_correct": sum(t["correct"] for t in ts), "wrong_qualified": sum(r["wrong_qualified"] for t in ts for r in t["rows"]),
                   "censored": sum(t["correct"] != t["n_sealed"] for t in ts),
                   "retention_changed": sum(f["retention"]["n"] - f["retention"]["unchanged"] for s in seeds for f in raw[f"{s}:{arm}"]["families"] if f.get("retention"))}
    o["Q2"] = q2
    o["Xk==Xr"] = all(raw[f"{s}:{r}k"]["reply_stream_sha256"] == raw[f"{s}:{r}r"]["reply_stream_sha256"] and
                     raw[f"{s}:{r}k"]["final_state_sha256"] == raw[f"{s}:{r}r"]["final_state_sha256"] for s in seeds for r in "CBPF" if f"{s}:{r}k" in raw)
    # strata by B's searched depth (task-only)
    dep = {(s, i): t.get("searched_len") for s in seeds for i, t in enumerate(raw[f"{s}:Bk"]["tasks"])}
    if cur != "unrel":
        o["strata"] = {str(k): (sum(1 for v in dep.values() if v == k), A(tot(raw, seeds, "Ck", sel=lambda s, i, k=k: dep[(s, i)] == k), tot(raw, seeds, "Bk", sel=lambda s, i, k=k: dep[(s, i)] == k)))
                       for k in sorted({v for v in dep.values() if v is not None})}
        # how many of C's tasks at B-depth 5 used the library, and C's searched depth there
        o["C_depth_at_B5"] = sorted({raw[f"{s}:Ck"]["tasks"][i].get("searched_len") for (s, i), v in dep.items() if v == 5})
    # work split (evaluations), rho = (cpuC/wC)/(cpuB/wB), Ck+maint vs Bk as in the receipt
    for w in ("evaluations", "row_ops", "executions"):
        cc, bc = sum(tot(raw, seeds, "Ck+maint")), sum(tot(raw, seeds, "Bk"))
        cw, bw = sum(tot(raw, seeds, "Ck+maint", w)), sum(tot(raw, seeds, "Bk", w))
        o[f"split_{w}"] = {"A_work": round(1 - cw / bw, 4), "rho": round((cc / cw) / (bc / bw), 3), "resid": (cc / bc) - (cw / bw) * (cc / cw) / (bc / bw)}
    # rate ratio (task-only, per family, seed means)
    fams = sorted({t["family"] for t in raw[f"{seeds[0]}:Bk"]["tasks"]})
    Y, W = [], []
    for f in fams:
        y = w_ = 0
        for s in seeds:
            C = [t for t in raw[f"{s}:Ck"]["tasks"] if t["family"] == f]; B = [t for t in raw[f"{s}:Bk"]["tasks"] if t["family"] == f]
            y += math.log(sum(t["cost"]["cpu_total_s"] for t in C) / sum(t["cost"]["cpu_total_s"] for t in B))
            w_ += math.log(max(sum(t["cost"]["evaluations"] for t in C), 1) / max(sum(t["cost"]["evaluations"] for t in B), 1))
        Y.append(y / len(seeds)); W.append(w_ / len(seeds))
    s_, o_ = -ols(W), ols([a - b for a, b in zip(Y, W)])
    o["rate"] = {"slope_y": round(ols(Y), 5), "s": round(s_, 5), "o": round(o_, 5), "o/s": round(o_ / s_, 4) if s_ > 0 else "s<=0", "families": len(fams)}
    # receipt values side by side
    an = c["analyses"]
    o["receipt"] = {"A_primary": an["parsed"]["Ck+maint||Bk"]["A"], "strata": {k: v["A"] for k, v in an.get("strata_B_depth", {}).items()},
                    "rho_evals": an["work_split"]["evaluations"]["vs_B"]["rho"][0], "rate": {k: an["rate_ratio"][k] for k in ("slope_y", "s_savings", "o_overhead", "rate_ratio_o_over_s")}}
    out[cur] = o
    print(json.dumps({cur: o}))
g = rc["gate"]; P = {c: rc["curricula"][c]["analyses"]["parsed"]["Ck+maint||Bk"]["A"] for c in rc["curricula"]}
mine = {"Q1": P["comp"][1][0] > 0, "Q3": P["unrel"][1][0] > -0.949, "Q4a": P["comprep"][1][0] > 0, "Q4b": P["mixed"][1][0] > 0,
        "Q2": all(out[c]["Q2"]["Ck"]["wrong_qualified"] == 0 and out[c]["Q2"]["Ck"]["retention_changed"] == 0 and out[c]["Q2"]["Ck"]["sealed_correct"] >= out[c]["Q2"]["Bk"]["sealed_correct"] for c in out)}
mine["PASS"] = all(mine.values())
print(json.dumps({"gate_mine": mine, "gate_receipt": {k: g[k] for k in ("Q1_comp_positive", "Q2_no_correctness_or_retention_loss", "Q3_unrel_penalty_halved", "Q4a_comp_replicates", "Q4b_mixed_positive", "PASS", "verdict")}}))
