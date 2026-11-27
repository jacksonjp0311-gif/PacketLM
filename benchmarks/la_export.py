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


def export(raw, out_csv, bytes_csv=None):
    rows, brows = [], []
    for key, run in raw.items():
        seed, arm = key.split(":")
        if arm == "R" or "tasks" not in run:
            continue
        fams = {f["family"]: f for f in run.get("families", [])}
        variants = [arm] + ([f"{arm}+maint"] if fams and any("cost" in f for f in fams.values()) else [])
        for var in variants:
            for comp in ("acquisition", "verification", "storage", "retrieval", "maintenance", "execution"):
                rows.append([var, seed, 0, comp, "cpu_s", 0.0, 0])
            last_of_family = {}
            for i, t in enumerate(run["tasks"], 1):
                last_of_family[t["family"]] = i
            for i, t in enumerate(run["tasks"], 1):
                cens = int(t["correct"] != t["n_sealed"])
                c = t["cost"]
                # the frozen engine reports CPU per call; component split by call type
                acq, exe = t.get("cpu_acquisition"), t.get("cpu_execution")
                if acq is None:
                    acq, exe = c["cpu_s"] - t.get("eval_cpu_s", 0.0), t.get("eval_cpu_s", 0.0)
                rows.append([var, seed, i, "acquisition", "cpu_s", round(acq, 6), cens])
                rows.append([var, seed, i, "execution", "cpu_s", round(exe, 6), cens])
                for comp in ("verification", "retrieval", "storage"):
                    rows.append([var, seed, i, comp, "cpu_s", 0.0, cens])
                m = 0.0
                if var.endswith("+maint") and last_of_family.get(t["family"]) == i:
                    m = fams.get(t["family"], {}).get("cost", {}).get("cpu_s", 0.0)
                rows.append([var, seed, i, "maintenance", "cpu_s", round(m, 6), cens])
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
    raw = json.loads(open(sys.argv[1]).read())
    print(export(raw, sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None))
