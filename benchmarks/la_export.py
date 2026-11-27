"""Export G46/G47 raw logs to the learning-amortization cost-log CSV (docs/LA_EXPORT.md).
Run: python3 benchmarks/la_export.py artifacts/g46/g46_raw.json OUT.csv [OUT_bytes.csv]
"""

from __future__ import annotations
import csv
import json
import sys


def classify(lines):
    if all(ln.startswith("what is ") for ln in lines):
        return "execution"
    return "acquisition"


def export(raw, out_csv, bytes_csv=None, res="cpu_s"):
    """res: "cpu_s" (engine work after startup) or "cpu_total_s" (whole process, from G48 on)."""
    rows, brows = [], []
    for name, run in raw.items():
        seed, arm = name.split(":")
        if arm == "R" or "tasks" not in run:
            continue
        fams = {f["family"]: f for f in run.get("families", [])}
        variants = [arm] + ([f"{arm}+maint"] if fams and any("cost" in f for f in fams.values()) else [])
        for var in variants:
            for comp in ("acquisition", "verification", "storage", "retrieval", "maintenance", "execution"):
                rows.append([var, seed, 0, comp, res, 0.0, 0])
            last_of_family = {}
            for i, t in enumerate(run["tasks"], 1):
                last_of_family[t["family"]] = i
            for i, t in enumerate(run["tasks"], 1):
                cens = int(t["correct"] != t["n_sealed"])
                c = t["cost"]
                # the frozen engine reports CPU per call; component split by call type
                acq, exe = t.get("cpu_acquisition"), t.get("cpu_execution")
                if acq is None:
                    ev = t.get("eval_cpu_s", 0.0) if res == "cpu_s" else t.get("eval_cpu_total_s", 0.0)
                    acq, exe = c[res] - ev, ev
                rows.append([var, seed, i, "acquisition", res, round(acq, 6), cens])
                rows.append([var, seed, i, "execution", res, round(exe, 6), cens])
                for comp in ("verification", "retrieval", "storage"):
                    rows.append([var, seed, i, comp, res, 0.0, cens])
                m = 0.0
                if var.endswith("+maint") and last_of_family.get(t["family"]) == i:
                    m = fams.get(t["family"], {}).get("cost", {}).get(res, 0.0)
                rows.append([var, seed, i, "maintenance", res, round(m, 6), cens])
                if bytes_csv and var == arm:
                    brows.append([arm, seed, i, "storage", "bytes", float(t.get("state_bytes") or 0), cens])
    with open(out_csv, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["arm", "seed", "task", "component", "resource", "amount", "censored"])
        w.writerows(rows)
    if bytes_csv:
        with open(bytes_csv, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["arm", "seed", "task", "component", "resource", "amount", "censored"])
            w.writerows(brows)
    return len(rows)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--total"]
    raw = json.loads(open(args[0]).read())
    print(export(raw, args[1], args[2] if len(args) > 2 else None, "cpu_total_s" if "--total" in sys.argv else "cpu_s"))
