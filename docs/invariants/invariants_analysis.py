"""Reproduce every number in docs/invariants/INVARIANTS.md from published evidence only (no engine runs).
Usage: python3 docs/invariants/invariants_analysis.py   (reads docs/evidence/g5*/; ~1 s; stdlib + numpy)."""
import csv, collections, gzip, json, math, random, statistics as st
import numpy as np, os, sys
sys.path.insert(0, os.getcwd())
E_ = "docs/evidence"

def scale():
    print("== I3/I4 part S scaling (per-seed log-log fits)")
    for exp in ("g57", "g57b"):
        d = json.load(open(f"{E_}/{exp}/scale/{exp}_scale_receipt.json"))
        tab = collections.defaultdict(dict)
        for r in d["runs"]:
            tab[(r["arm"], r["seed"])][r["n"]] = r
        N = np.array(d["sizes"], float)
        for a in sorted({r["arm"] for r in d["runs"]}):
            seeds = sorted(s for (aa, s) in tab if aa == a)
            Y = np.array([[tab[(a, s)][n]["mean_task_cpu_s"] * 1e3 for n in d["sizes"]] for s in seeds])
            sl = [np.polyfit(np.log(N[1:]), np.log(y[1:]), 1)[0] for y in Y]
            m = Y.mean(0); ex = m[1:] - m[0]
            loc = math.log(ex[2] / ex[1], 4)
            slope = ex[2] / (N[3]) if ex[2] > 0 else float("nan")
            out = f"  {exp} X{a}: mean ms {np.round(m,3)}; loglog slope 1k..16k {np.mean(sl):.3f} (sd {np.std(sl,ddof=1):.3f}); local exponent of excess 4k->16k {loc:.3f}; excess per padding fact at 16k {slope*1e3:.3f} us"
            for key in ("pad_cpu_s", "snapshot_cpu_s"):
                if key in tab[(a, seeds[0])][1000]:
                    mm = np.mean([[tab[(a, s)][n][key] for n in d["sizes"]] for s in seeds], 0)
                    out += f"; {key} 4k->16k exponent {math.log(mm[3]/mm[2],4):.2f}"
            print(out)

def raw(exp, cur):
    return json.load(gzip.open(f"{E_}/{exp}/{cur}_raw.json.gz"))

def counters():
    print("== I1 logical work identical across modes (i vs j); I5/I6 interaction and evaluation ratios")
    d = raw("g57b", "comp"); same = tot = 0; whole = 0
    for k, r in d.items():
        s, a = k.split(":")
        if a.endswith("j"):
            ri = d[s + ":" + a[0] + "i"]
            whole += (r["interactions"], r["processes"], r["final_state_bytes"]) == (ri["interactions"], ri["processes"], ri["final_state_bytes"])
            for fj, fi in zip(r["families"], ri["families"]):
                if "cost" in fj:
                    tot += 1
                    same += all(fj["cost"][x] == fi["cost"][x] for x in ("evaluations", "executions", "row_ops", "asks", "processes", "lines"))
    print(f"  g57b comp: family counters identical i vs j {same}/{tot}; run-level (interactions, processes, state bytes) identical {whole}/28")
    for exp, (c, b, p) in {"g53": ("Cb", "Bb", "Pb"), "g54": ("Cl", "Bl", "Pl"), "g56": ("Cs", "Bs", "Ps"), "g57": ("Ci", "Bi", "Pi"), "g57b": ("Cj", "Bj", "Pj")}.items():
        for cur in ("comp", "unrel"):
            d = raw(exp, cur); g = collections.defaultdict(collections.Counter)
            for k, r in d.items():
                a = k.split(":")[1]; g[a]["int"] += r["interactions"]
                for f in r["families"]:
                    if "cost" in f:
                        g[a]["ev"] += f["cost"]["evaluations"]
            ev = g[c]["ev"] / g[p]["ev"] if g[p]["ev"] else float("nan")
            asks = sum(f["cost"]["asks"] for k, r in d.items() if k.endswith(":" + c) for f in r["families"] if "cost" in f)
            print(f"  {exp} {cur}: C probe asks {asks}; lines minus probe asks C/B {(g[c]['int']-asks)/g[b]['int']:.3f};", end="")
            print(f"  lines C/B {g[c]['int']}/{g[b]['int']} = {g[c]['int']/g[b]['int']:.3f}; evaluations C/P {ev:.3f}")

def shapes():
    print("== I7 per-shape cost ratios (C+maint/B, C+maint/P+maint), comp")
    d = raw("g57b", "comp"); shape = {i + 1: (t["phase"], t["shape"]) for i, t in enumerate(d["241:Cj"]["tasks"])}
    pairs = {"g54": ("Cl+maint", "Bl", "Pl+maint"), "g56": ("Cs+maint", "Bs", "Ps+maint"), "g57": ("Ci+maint", "Bi", "Pi+maint"), "g57b": ("Cj+maint", "Bj", "Pj+maint")}
    res = collections.defaultdict(dict)
    for exp, (c, b, p) in pairs.items():
        tot = collections.defaultdict(float)
        for row in csv.DictReader(open(f"{E_}/{exp}/comp_total.csv")):
            t = int(row["task"])
            if t in shape:
                tot[(row["arm"], shape[t])] += float(row["amount"])
        for sh in set(shape.values()):
            res[sh][exp] = (round(tot[(c, sh)] / tot[(b, sh)], 2), round(tot[(c, sh)] / tot[(p, sh)], 2))
    for sh in sorted(res):
        print("  ", sh, res[sh])
    print("== E search depth by shape (searched_len), g57b comp")
    for a in ("Cj", "Bj"):
        c = collections.Counter((t["shape"], t["searched_len"]) for k, r in d.items() if k.endswith(":" + a) for t in r["tasks"])
        print("  ", a, sorted(c.items()))

def within_run():
    print("== I8 within-run trend of per-task log(C+maint/B) (summed over seeds)")
    pairs = {"g54": ("Cl+maint", "Bl"), "g56": ("Cs+maint", "Bs"), "g57": ("Ci+maint", "Bi"), "g57b": ("Cj+maint", "Bj")}
    for exp, (c, b) in pairs.items():
        for cur in ("comp", "unrel"):
            tot = collections.defaultdict(float)
            for row in csv.DictReader(open(f"{E_}/{exp}/{cur}_total.csv")):
                tot[(row["arm"], int(row["task"]))] += float(row["amount"])
            T = max(k[1] for k in tot) + 1
            C = np.array([tot[(c, t)] for t in range(T)]); B = np.array([tot[(b, t)] for t in range(T)])
            ok = (C > 0) & (B > 0); t = np.arange(T)[ok]
            sl = np.polyfit(t, np.log(C[ok] / B[ok]), 1)[0]
            th = [C[i:i + T // 3].sum() / B[i:i + T // 3].sum() for i in range(0, 3 * (T // 3), T // 3)]
            print(f"  {exp} {cur}: slope {sl:+.4f}/task; C/B by thirds {np.round(th,2)}")

def emergence():
    print("== E1 capability reuse distribution (Cj, g57b comp)")
    d = raw("g57b", "comp"); hist = collections.Counter(); per = []
    for k, r in d.items():
        if k.endswith(":Cj"):
            u = collections.Counter(s for t in r["tasks"] for s in (t["seq"] or []) if s.startswith("cap:"))
            hist.update(collections.Counter(u.values())); per.append(tuple(sorted(u.values(), reverse=True)))
    print(f"  uses->caps {sorted(hist.items())}; distinct per-seed profiles {len(set(per))}")
    print("== E3/E5 corrections and retention (g57b)")
    for cur in ("comp", "unrel"):
        d = raw("g57b", cur); g = collections.Counter()
        for k, r in d.items():
            if k.endswith(":Cj"):
                for f in r["families"]:
                    c = f.get("correction") or {}; rt = f.get("retention") or {}
                    g["affected"] += c.get("affected", 0); g["propagated"] += c.get("propagated", 0)
                    g["ret_n"] += rt.get("n", 0); g["ret_changed"] += len(rt.get("changed", []))
        print("  ", cur, dict(g))
    print("== R1 packet density (simulation, 20000 random triples)")
    from packetlm.field import bits_for
    rng = random.Random(1); tok = lambda: "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(6))
    pc = [bin(bits_for(tok(), 0) ^ bits_for(tok(), 1) ^ bits_for(tok(), 2)).count("1") for _ in range(20000)]
    a = [bits_for(tok(), 0) for _ in range(2000)]; b = [bits_for(tok(), 1) for _ in range(200)]
    ov = sum(bin(x & y).count("1") >= 2 for x in a for y in b) / (2000 * 200)
    print(f"  popcount mean {st.mean(pc):.2f} sd {st.pstdev(pc):.2f} min {min(pc)}; P(two codes share >=2 bits) {ov:.5f} (theory ~C(16,2)/256^2 = {120/65536:.5f})")

if __name__ == "__main__":
    scale(); counters(); shapes(); within_run(); emergence()
