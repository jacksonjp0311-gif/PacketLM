"""Recompute G60H gate analyses from the registered raw files with the pinned instrument; compare to receipts."""
import gzip, json, sys, tempfile, shutil
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "benchmarks"), str(ROOT)]
import g60h, g59, g59_analysis as G
from la_export import export
out = {}
for m in ("m1", "m2"):
    E = ROOT / f"docs/evidence/g60h/gate_{m}"
    rec = json.load(open(E / f"g60h_reg_{m}_receipt.json"))
    tmp = Path(tempfile.mkdtemp())
    q = {}
    for c in g60h.SEEDS:
        raw = json.load(gzip.open(E / f"{c}_raw.json.gz"))
        seeds = rec["seeds"][c]
        csvs = {}
        for r_ in ("cpu_total_s", "evaluations", "lines"):
            csvs[r_] = tmp / f"{c}_{r_}.csv"
            export(raw, csvs[r_], None, r_) if r_ == "cpu_total_s" else G.export_resource(raw, csvs[r_], r_)
        # registered csv byte-equal?
        reg = gzip.open(E / f"{c}_cpu_total_s.csv.gz").read()
        same_csv = reg == csvs["cpu_total_s"].read_bytes()
        arms = ["Ch", "Bh", "Ph"]
        n = len(raw[f"{seeds[0]}:Ch"]["tasks"])
        per, outcomes, _ = g59.summarize(raw, seeds, arms, [])
        an = g60h.analyses(raw, seeds, csvs, n)
        q[c] = {"analyses": an, "outcomes": outcomes}
        R = rec["curricula"][c]["analyses"]
        cmp = []
        for k in ("primary", "secondary"):
            for x, y in zip(an[k], R[k]):
                cmp.append((x["cont"], x["base"], x["report"].splitlines()[0] == y["report"].splitlines()[0], x["report"].splitlines()[0]))
        res_eq = all(a["report"].splitlines()[0] == b["report"].splitlines()[0] for r_ in an["resources"] for a, b in zip(an["resources"][r_], R["resources"][r_]))
        other = {k: json.dumps(an[k], sort_keys=True, default=str) == json.dumps(R[k], sort_keys=True, default=str)
                 for k in ("work_split", "maintenance_share", "strata_B_depth", "censoring", "rate_ratio", "in_run", "emergence")}
        oc = json.dumps(outcomes, sort_keys=True, default=str) == json.dumps(rec["curricula"][c]["outcomes"], sort_keys=True, default=str)
        out[f"{m}:{c}"] = {"csv_byte_equal": same_csv, "contrasts": cmp, "resources_equal": res_eq, "other_equal": other, "outcomes_equal": oc}
        print(m, c, "csv", same_csv, "contrasts", sum(x[2] for x in cmp), "/", len(cmp), "res", res_eq, "outcomes", oc, other, flush=True)
    g = g60h.gate(q)
    out[f"{m}:gate_equal"] = json.dumps(g, sort_keys=True, default=str) == json.dumps(rec["gate"], sort_keys=True, default=str)
    out[f"{m}:gate"] = g
    print(m, "gate equal", out[f"{m}:gate_equal"], g["verdict"], flush=True)
    shutil.rmtree(tmp)
Path(ROOT / "tools_69b5b26/repro_out.json").write_text(json.dumps(out, indent=1, default=str))
