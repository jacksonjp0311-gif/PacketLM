"""G59 pre-registered analyses (docs/G59.md §6), on the per-arm raw files of a run. Pure functions
of the raw data (no engine runs); the same code computes the predictions from G58's published raw
files (docs/evidence/g58) before the run.

Cost of a task = its calls' whole-process CPU (`cost.cpu_total_s`); an arm "X+maint" adds each
family's maintenance calls (correction, transfer, retention probes) to the family's last task, as
benchmarks/la_export.py does. Seed bootstrap: 5000 resamples of whole seeds, the same indices for
both arms (paired), percentile 95% intervals; seed 0.
"""
from __future__ import annotations
import math
import random
import re

REPS = 5000


def task_costs(run, res="cpu_total_s", maint=False):
    """Per-task cost list of one arm run (task order), maintenance folded into each family's last task."""
    tasks = run["tasks"]
    out = [t["cost"].get(res, 0.0) for t in tasks]
    if maint:
        last = {}
        for i, t in enumerate(tasks):
            last[t["family"]] = i
        for f in run.get("families", []):
            if "cost" in f and f["family"] in last:
                out[last[f["family"]]] += f["cost"].get(res, 0.0)
    return out


def _arm(raw, seed, arm):
    a, plus = (arm[:-6], True) if arm.endswith("+maint") else (arm, False)
    return raw[f"{seed}:{a}"], plus


def boot_ratio(num, den, reps=REPS, seed=0):
    """A = 1 - sum(num)/sum(den) over seeds (ratio of totals), percentile CI by seed resampling."""
    S = len(num)
    a = 1 - sum(num) / sum(den)
    rng = random.Random(seed)
    v = []
    for _ in range(reps):
        ix = [rng.randrange(S) for _ in range(S)]
        d = sum(den[i] for i in ix)
        v.append(1 - sum(num[i] for i in ix) / d if d else float("nan"))
    v = sorted(x for x in v if x == x)
    return round(a, 4), [round(v[int(0.025 * len(v))], 4), round(v[int(0.975 * len(v)) - 1], 4)]


def totals(raw, seeds, arm, res="cpu_total_s", sel=None):
    out = []
    for s in seeds:
        run, plus = _arm(raw, s, arm)
        c = task_costs(run, res, plus)
        out.append(sum(x for i, x in enumerate(c) if sel is None or sel(s, i)))
    return out


def A(raw, seeds, cont, base, res="cpu_total_s", sel=None):
    return boot_ratio(totals(raw, seeds, cont, res, sel), totals(raw, seeds, base, res, sel))


def work_split(raw, seeds, cont, base, work="evaluations"):
    """1 - A_cpu = (1 - A_work) * rho, rho = per-op cost ratio (CPU per unit of work, cont / base).
    A_cpu and A_work with CIs; rho's CI from the same paired resamples."""
    c_cpu, b_cpu = totals(raw, seeds, cont), totals(raw, seeds, base)
    c_w, b_w = totals(raw, seeds, cont, work), totals(raw, seeds, base, work)
    S, rng = len(seeds), random.Random(0)
    rho = lambda ix: (sum(c_cpu[i] for i in ix) / sum(c_w[i] for i in ix)) / (sum(b_cpu[i] for i in ix) / sum(b_w[i] for i in ix))  # noqa: E731
    v = sorted(rho([rng.randrange(S) for _ in range(S)]) for _ in range(REPS))
    r0 = rho(range(S))
    a_cpu, a_w = boot_ratio(c_cpu, b_cpu), boot_ratio(c_w, b_w)
    exact = (sum(c_cpu) / sum(b_cpu)) - (sum(c_w) / sum(b_w)) * r0  # (1 - A_cpu) - (1 - A_work) rho, unrounded
    return {"work": work, "A_cpu": a_cpu, "A_work": a_w, "rho": [round(r0, 4), [round(v[int(0.025 * REPS)], 4), round(v[int(0.975 * REPS) - 1], 4)]],
            "identity_residual": exact}


def b_depth(raw, seeds, base="Bk"):
    """(seed, task index) -> the reference arm's searched length (the depth B needed)."""
    return {(s, i): t.get("searched_len") for s in seeds for i, t in enumerate(raw[f"{s}:{base}"]["tasks"])}


def strata(raw, seeds, cont, base):
    """A(cont || base) per stratum of the reference's searched depth, task-only costs."""
    d = b_depth(raw, seeds, base.replace("+maint", ""))
    out = {}
    for k in sorted({v for v in d.values() if v is not None}):
        n = sum(1 for v in d.values() if v == k)
        out[str(k)] = {"tasks": n, "A": A(raw, seeds, cont.replace("+maint", ""), base, sel=lambda s, i, k=k: d[(s, i)] == k)}
    return out


def censoring(raw, seeds, cont, base):
    """Prop. 6 of the instrument (censoring bounds): counts per arm, the direction of the bound, and the
    matched subset (tasks censored in neither arm, same seed) -- descriptive only: dropping censored
    tasks is selection on the outcome."""
    cens = lambda arm: {(s, i) for s in seeds for i, t in enumerate(raw[f"{s}:{arm}"]["tasks"]) if t["correct"] != t["n_sealed"]}  # noqa: E731
    c, b = cens(cont.replace("+maint", "")), cens(base.replace("+maint", ""))
    direction = "exact" if not c and not b else "lower bound (only the reference is censored)" if not c else \
        "upper bound (only the learner is censored)" if not b else "undetermined (both censored)"
    n = sum(len(raw[f"{s}:{base.replace('+maint', '')}"]["tasks"]) for s in seeds)
    matched = A(raw, seeds, cont.replace("+maint", ""), base.replace("+maint", ""), sel=lambda s, i: (s, i) not in c and (s, i) not in b)
    return {"censored_cont": len(c), "censored_base": len(b), "tasks": n, "recorded_A_is": direction,
            "matched_subset_tasks": n - len(c | b), "A_matched_task_only": matched}


def _ols(y):
    n = len(y)
    xm, ym = (n - 1) / 2, sum(y) / n
    sxx = sum((i - xm) ** 2 for i in range(n))
    return sum((i - xm) * (v - ym) for i, v in enumerate(y)) / sxx, ym - xm * sum((i - xm) * (v - ym) for i, v in enumerate(y)) / sxx


def rate_ratio(raw, seeds, cont, base, work="evaluations"):
    """James's accumulation hypothesis, per family f (sums over the family's tasks; task-only):
    y_f = ln(C_f/B_f) (CPU), w_f = ln(W^C_f / W^B_f) (work), o_f = y_f - w_f (per-op cost ratio).
    Savings-compounding rate s = -slope(w), overhead-growth rate o = slope(o_f), slope(y) = o - s.
    Slopes: OLS over f of the seed means; CIs by seed resampling. Predicted crossover family f* where
    the fitted y line reaches 0 (none if slope(y) >= 0 and y > 0)."""
    fams = sorted({t["family"] for t in raw[f"{seeds[0]}:{base}"]["tasks"]})

    def per_seed(s):
        C, B = raw[f"{s}:{cont}"]["tasks"], raw[f"{s}:{base}"]["tasks"]
        y, w = [], []
        for f in fams:
            cc = sum(t["cost"]["cpu_total_s"] for t in C if t["family"] == f)
            bb = sum(t["cost"]["cpu_total_s"] for t in B if t["family"] == f)
            cw = sum(t["cost"][work] for t in C if t["family"] == f)
            bw = sum(t["cost"][work] for t in B if t["family"] == f)
            y.append(math.log(cc / bb))
            w.append(math.log(max(cw, 1) / max(bw, 1)))
        return y, w
    P = {s: per_seed(s) for s in seeds}

    def stats(ix):
        y = [sum(P[seeds[i]][0][f] for i in ix) / len(ix) for f in range(len(fams))]
        w = [sum(P[seeds[i]][1][f] for i in ix) / len(ix) for f in range(len(fams))]
        o = [a - b for a, b in zip(y, w)]
        sy, iy = _ols(y)
        return {"slope_y": sy, "s_savings": -_ols(w)[0], "o_overhead": _ols(o)[0], "y_first": y[0], "y_last": y[-1], "icpt_y": iy}
    S, rng = len(seeds), random.Random(0)
    pt = stats(list(range(S)))
    bs = [stats([rng.randrange(S) for _ in range(S)]) for _ in range(REPS)]
    ci = lambda k: [round(sorted(b[k] for b in bs)[int(0.025 * REPS)], 5), round(sorted(b[k] for b in bs)[int(0.975 * REPS) - 1], 5)]  # noqa: E731
    out = {k: [round(pt[k], 5), ci(k)] for k in ("slope_y", "s_savings", "o_overhead", "y_first", "y_last")}
    out["rate_ratio_o_over_s"] = round(pt["o_overhead"] / pt["s_savings"], 4) if pt["s_savings"] > 0 else "s <= 0"
    if pt["slope_y"] < 0:
        f_star = -pt["icpt_y"] / pt["slope_y"]
        out["predicted_crossover_family"] = round(f_star, 2)
        out["predicted_crossover_task"] = round(6 * (f_star + 1), 1)
    else:
        out["predicted_crossover_family"] = None  # no crossover: the gap does not shrink
    out["families"] = len(fams)
    return out


REPORT = re.compile(r"A_(\d+) = ([+-][\d.]+)\s+\[([+-][\d.]+), ([+-][\d.]+)\]")
TREND = re.compile(r"trend of per-task log ratio: ([+-][\d.]+) per task\s+\[([+-][\d.]+), ([+-][\d.]+)\]")


def parse(report):
    m, t = REPORT.search(report or ""), TREND.search(report or "")
    out = {"A": [float(m.group(2)), [float(m.group(3)), float(m.group(4))]] if m else None,
           "beta": [float(t.group(1)), [float(t.group(2)), float(t.group(3))]] if t else None}
    cm = re.search(r"A_n curve \(seed-mean costs\): \[([^\]]*)\]", report or "", re.S)
    out["A_n_curve"] = [float(x) for x in cm.group(1).split()] if cm else None
    return out


def reuse(raw, seeds, cont):
    """Emergence log `reuse` and `depth`: capability steps per task's final version; histogram of
    uses per capability, max, Gini, distinct per-seed profiles; searched-length histograms."""
    profiles, all_uses = set(), []
    for s in seeds:
        uses = {}
        for t in raw[f"{s}:{cont}"]["tasks"]:
            for st in t.get("seq") or []:
                if st.startswith("cap:"):
                    nm = st.split("@")[0][4:]
                    uses[nm] = uses.get(nm, 0) + 1
        prof = tuple(sorted(uses.values()))
        profiles.add(prof)
        all_uses += list(uses.values())
    hist = {}
    for u in all_uses:
        hist[str(u)] = hist.get(str(u), 0) + 1
    xs = sorted(all_uses)
    n = len(xs)
    gini = round(sum((2 * (i + 1) - n - 1) * x for i, x in enumerate(xs)) / (n * sum(xs)), 4) if n and sum(xs) else None
    return {"uses_to_caps_histogram": hist, "max_uses": max(xs) if xs else 0, "gini": gini,
            "distinct_profiles_across_seeds": len(profiles), "capabilities_used": n}


def depth_hist(raw, seeds, arm):
    h = {}
    for s in seeds:
        for t in raw[f"{s}:{arm}"]["tasks"]:
            k = str(t.get("searched_len"))
            h[k] = h.get(k, 0) + 1
    return h


def cascades(raw, seeds, arm):
    aff, prop, mx = 0, 0, 0
    for s in seeds:
        for f in raw[f"{s}:{arm}"]["families"]:
            c = f.get("correction")
            if c:
                aff += c["affected"]
                prop += c["propagated"]
                mx = max(mx, c["affected"])
    return {"affected": aff, "propagated": prop, "max_single_correction": mx}


def retention(raw, seeds, arm):
    n = ch = 0
    for s in seeds:
        for f in raw[f"{s}:{arm}"]["families"]:
            r = f.get("retention")
            if r:
                n += r["n"]
                ch += r["n"] - r["unchanged"]
    return {"changed": ch, "n": n}


def in_run(raw, seeds, cont, base):
    """Slope of the seed-mean per-task log ratio ln(C_i/B_i) over i, and C/B by thirds (task-only)."""
    n = len(raw[f"{seeds[0]}:{base}"]["tasks"])
    y = []
    for i in range(n):
        v = [math.log(raw[f"{s}:{cont}"]["tasks"][i]["cost"]["cpu_total_s"] / raw[f"{s}:{base}"]["tasks"][i]["cost"]["cpu_total_s"]) for s in seeds]
        y.append(sum(v) / len(v))
    th = []
    for k in range(3):
        sl = range(k * n // 3, (k + 1) * n // 3)
        c = sum(raw[f"{s}:{cont}"]["tasks"][i]["cost"]["cpu_total_s"] for s in seeds for i in sl)
        b = sum(raw[f"{s}:{base}"]["tasks"][i]["cost"]["cpu_total_s"] for s in seeds for i in sl)
        th.append(round(c / b, 4))
    return {"slope_log_CB_per_task": round(_ols(y)[0], 5), "C/B_by_thirds": th}


def export_resource(raw, out_csv, res):
    """benchmarks/la_export.py's cost-log CSV for a work resource (`evaluations`, `lines`): the same
    rows, arms (X and X+maint), censoring flags and maintenance placement, with the task's whole
    amount as acquisition (la_export's CPU split by call type does not apply to counts)."""
    import csv
    rows = []
    for name, run in raw.items():
        seed, arm = name.split(":")
        fams = {f["family"]: f for f in run.get("families", [])}
        variants = [arm] + ([f"{arm}+maint"] if fams and any("cost" in f for f in fams.values()) else [])
        for var in variants:
            for comp in ("acquisition", "verification", "storage", "retrieval", "maintenance", "execution"):
                rows.append([var, seed, 0, comp, res, 0.0, 0])
            last = {}
            for i, t in enumerate(run["tasks"], 1):
                last[t["family"]] = i
            for i, t in enumerate(run["tasks"], 1):
                cens = int(t["correct"] != t["n_sealed"])
                rows.append([var, seed, i, "acquisition", res, float(t["cost"].get(res, 0)), cens])
                for comp in ("execution", "verification", "retrieval", "storage"):
                    rows.append([var, seed, i, comp, res, 0.0, cens])
                m = 0.0
                if var.endswith("+maint") and last.get(t["family"]) == i:
                    m = float(fams.get(t["family"], {}).get("cost", {}).get(res, 0))
                rows.append([var, seed, i, "maintenance", res, m, cens])
    with open(out_csv, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["arm", "seed", "task", "component", "resource", "amount", "censored"])
        w.writerows(rows)
    return len(rows)
