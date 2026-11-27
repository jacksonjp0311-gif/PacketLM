"""Sensitivity (verifier, unregistered): on tasks where Ch's final 'qualified' would be ambiguous under the
base-language uniqueness rule (B's rule) on the same evidence (shadow B1), charge Ch the Ph cost of that task."""
import json, gzip, sys, tempfile, copy
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "benchmarks"), str(ROOT)]
from la_export import export
from g51 import instrument
D = sys.argv[1]; M = sys.argv[2]
out = {}
for cur in ("comp", "comprep", "mixed", "long", "unrel"):
    raw = json.load(gzip.open(ROOT / f"docs/evidence/g60h/gate_m{M}/{cur}_raw.json.gz"))
    seeds = sorted({int(k.split(":")[0]) for k in raw})
    nflag = 0; ntask = 0
    for s in seeds:
        last = {}
        for line in open(f"{D}/{cur}_{s}_Ch.jsonl"):
            r = json.loads(line); last[r["name"]] = r
        flagged = {n for n, r in last.items() if r["real"]["result"] == "qualified" and not (r["B1"]["result"] == "qualified" and r["B1"].get("tuple") == r["real"]["tuple"])}
        C, B, PP = raw[f"{s}:Ch"], raw[f"{s}:Bh"], raw[f"{s}:Ph"]
        for i, t in enumerate(C["tasks"]):
            ntask += 1
            if t["name"] in flagged:
                b = PP["tasks"][i]; assert b["name"] == t["name"]
                t["cost"] = dict(t["cost"], cpu_total_s=b["cost"]["cpu_total_s"]); t["eval_cpu_total_s"] = b["eval_cpu_total_s"]
                nflag += 1
    tmp = Path(tempfile.mkdtemp()) / f"{cur}.csv"
    export(raw, tmp, None, "cpu_total_s")
    n = len(raw[f"{seeds[0]}:Ch"]["tasks"])
    res = {f"{a}||{b}": instrument(tmp, a, b, n)["report"].splitlines()[0] for a, b in [("Ch+maint", "Bh"), ("Ch+maint", "Ph+maint"), ("Ch", "Bh")]}
    out[cur] = {"flagged_tasks": nflag, "tasks": ntask, **res}
    print(cur, nflag, "/", ntask, json.dumps(res, indent=0), flush=True)
Path(f"{D}/substP_m{M}.json").write_text(json.dumps(out, indent=1))
