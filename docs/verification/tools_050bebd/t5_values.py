import json, subprocess, sys, shutil
for seed in (101,202,303):
    r=json.load(open(f"/workspace/pl-verify-logs/v6/t5/r{seed}.json"))
    rows=[x for d in r["domains"] for x in d["rows"]]
    sp=f"/tmp/t5_{seed}.json"; shutil.copy(f"/workspace/pl-verify-logs/v6/t5/g45_{seed}.json", sp)
    p=subprocess.run([sys.executable,"-m","packetlm.engine",sp,*[f"what is {x['s']} {x['name']}" for x in rows]],capture_output=True,text=True)
    after=json.loads(p.stdout)["replies"]
    ch=[(x,a) for x,a in zip(rows,after) if x["reply"]!=a]
    strip=lambda s:s.replace(" [provisional]","")
    print(seed,"items",len(rows),"changed",len(ch),"caps",{x["name"] for x,_ in ch},
          "all value-identical",all(strip(x["reply"])==strip(a) for x,a in ch),
          "all now provisional",all(a.endswith("[provisional]") for x,a in ch),
          "values==truth",all(x["got"]==x["truth"] for x,_ in ch))
    if ch: print("  e.g.",repr(ch[0][0]["reply"]),"->",repr(ch[0][1]))
