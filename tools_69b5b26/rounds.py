"""Teacher interaction per task (evidence items, investigate asks, calls) and CPU split: Ch vs Bh."""
import json, gzip, collections, statistics as st
for m in ("m1", "m2"):
    for cur in ("comp", "long", "unrel"):
        raw = json.load(gzip.open(f"docs/evidence/g60h/gate_{m}/{cur}_raw.json.gz"))
        agg = collections.defaultdict(lambda: collections.Counter())
        for k, v in raw.items():
            a = v["arm"]
            for t in v["tasks"]:
                agg[a]["tasks"] += 1
                agg[a]["evidence"] += len(t["evidence"])
                agg[a]["asked"] += len(t["asked"])
                agg[a]["cpu_task"] += t["cost"].get("cpu_total_s", 0)
                agg[a]["evals"] += t["cost"].get("evaluations", 0)
                agg[a]["lines"] += t["cost"].get("lines", 0)
                agg[a]["calls"] += t["cost"].get("calls", 0)
        print(m, cur, {a: {k: round(v, 3) for k, v in c.items()} for a, c in sorted(agg.items())})
raw = json.load(gzip.open("docs/evidence/g60h/gate_m1/comp_raw.json.gz"))
print(list(raw["401:Ch"]["tasks"][3]["cost"].keys()))
