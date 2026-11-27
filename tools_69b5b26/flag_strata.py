import json, gzip, collections
for cur in ("comp", "long"):
    raw = json.load(gzip.open(f"docs/evidence/g60h/gate_m1/{cur}_raw.json.gz"))
    seeds = sorted({int(k.split(":")[0]) for k in raw})
    c = collections.Counter(); tot = collections.Counter(); cpu = collections.Counter()
    for s in seeds:
        last = {}
        for line in open(f"/tmp/v69/sh_m1/{cur}_{s}_Ch.jsonl"):
            r = json.loads(line); last[r["name"]] = r
        for i, t in enumerate(raw[f"{s}:Ch"]["tasks"]):
            b = raw[f"{s}:Bh"]["tasks"][i]; d = b["searched_len"]
            r = last.get(t["name"]); tot[d] += 1
            fl = r and r["real"]["result"] == "qualified" and not (r["B1"]["result"] == "qualified" and r["B1"].get("tuple") == r["real"]["tuple"])
            if fl:
                c[d] += 1; cpu["flag_B"] += b["cost"]["cpu_total_s"]; cpu["flag_C"] += t["cost"]["cpu_total_s"]
            cpu["all_B"] += b["cost"]["cpu_total_s"]; cpu["all_C"] += t["cost"]["cpu_total_s"]
            if fl: cpu[("uses_lib", t["uses_library"])] += 1
    print(cur, "flagged by B depth", dict(sorted(c.items())), "of", dict(sorted(tot.items())), {str(k): round(v, 3) if isinstance(v, float) else v for k, v in cpu.items()})
