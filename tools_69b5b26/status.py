import json,gzip,sys,collections
for m in ("m1","m2"):
  for cur in ("comp","comprep","unrel","mixed","long"):
    raw=json.load(gzip.open(f"docs/evidence/g60h/gate_{m}/{cur}_raw.json.gz"))
    c=collections.Counter(); prov=collections.Counter(); seal=collections.Counter()
    for k,v in raw.items():
      a=v["arm"]
      for t in v["tasks"]:
        c[(a,t["status"],t["acquired"])]+=1
        for r in t["rows"]:
          seal[(a,"prov" if r["provisional"] else "qual", r["ok"])]+=1
    print(m,cur,sorted(c.items()))
    print("   sealed rows (arm,prov/qual,ok):",sorted(seal.items()))
