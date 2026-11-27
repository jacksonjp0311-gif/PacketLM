import json, subprocess, sys, tempfile, os
for seed in (101,202,303):
    r=json.load(open(f"/workspace/pl-verify-logs/v6/t5/r{seed}.json"))
    dem=r["retention_demoted"][0]
    st=json.load(open(f"/workspace/pl-verify-logs/v6/t5/g45_{seed}.json"))["state"]
    e=[d for d in r["domains"] if d["domain"]==5][0]["hidden"][-1]
    told=[f for f in st["facts"] if not f["r"].startswith("cap:") and any(s["kind"]=="told" for s in f["supports"])]
    obs=st["observations"][dem]
    for label,facts in (("all facts",told),("without D5 e-facts",[f for f in told if f["r"]!=e])):
        d=tempfile.mkdtemp(); sp=os.path.join(d,"s.json")
        lines=[f"fact {f['s']} {f['r']} {f['o']}" for f in facts]+[f"example {dem}: {s} -> {v}" for s,v in obs]
        p=subprocess.run([sys.executable,"-m","packetlm.engine",sp,*lines],capture_output=True,text=True)
        out=json.loads(p.stdout); s2=json.load(open(sp))["state"]
        print(seed,label,len(facts),out["replies"][-1][:90],"blockers:",s2["hypotheses"][dem].get("blocking"))
