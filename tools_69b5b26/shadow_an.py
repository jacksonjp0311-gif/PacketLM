import json, glob, collections, sys, os
D = sys.argv[1]
res = {}
for cur in ("comp", "comprep", "unrel", "mixed", "long"):
    for arm in ("Ch", "Bh", "Ph"):
        fin = collections.Counter(); allc = collections.Counter()
        for f in sorted(glob.glob(f"{D}/{cur}_*_{arm}.jsonl")):
            last = {}
            for line in open(f):
                r = json.loads(line)
                last[r["name"]] = r
                for tag in ("B1", "B5", "C5"):
                    if tag in r and r["real"]["result"] == "qualified":
                        s = r[tag]
                        same = s["result"] == "qualified" and s.get("tuple") == r["real"]["tuple"]
                        allc[(tag, "agree" if same else s["result"] + ("" if s.get("tuple") in (None, r["real"].get("tuple")) else "/other"))] += 1
            for r in last.values():
                fin[("final", r["real"]["result"])] += 1
                if r["real"]["result"] != "qualified":
                    continue
                for tag in ("B1", "B5", "C5"):
                    if tag not in r:
                        continue
                    s = r[tag]
                    same = s["result"] == "qualified" and s.get("tuple") == r["real"]["tuple"]
                    inlive = r["real"]["tuple"] in s["found_tuples"]
                    fin[(tag, "agree" if same else s["result"] + ("" if inlive else "/real-not-found"))] += 1
        if fin:
            res[f"{cur}:{arm}"] = {"final": {"|".join(k): v for k, v in sorted(fin.items())},
                                   "all_qualified_acquires": {"|".join(k): v for k, v in sorted(allc.items())}}
            print(cur, arm, dict(sorted(fin.items())))
json.dump(res, open(f"{D}/summary.json", "w"), indent=1)
