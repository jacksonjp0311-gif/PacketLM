import subprocess, shutil, sys
from pathlib import Path
E=Path('/tmp/v69/mutclone/packetlm/hdc/engine.py'); S=Path('/tmp/v69/mutclone/packetlm/hdc/serve.py')
M=[("library_ignored",E,"        if self.library:\n            caps = set()","        if True:\n            caps = set()"),
   ("no_blocking",E,'status = "provisional" if blockers else "qualified"','status = "qualified"'),
   ("no_prune",E,"if any(not t2[i] for i in vi):","if False:"),
   ("no_dedupe",E,"                    if t2 in seen:\n                        continue","                    pass"),
   ("domain_ignored",E,'prov = ver["status"] == "provisional" or s not in ver["domain"]','prov = ver["status"] == "provisional"'),
   ("decode_unchecked",E,"        if dec != exact:","        if False:"),
   ("touched_check_off",E,'assert C.unbind(k, C.rho(self.prim.code[r])) == self.ent.code[s], "fact key does not unbind to its subject"\n            assert all(v in self.ent.name for v in self.facts[k]), "fact value without a clean code"','pass'),
   ("full_check_off",E,'assert all(self.sig.get(s) == v for s, v in sig.items()), "signature bundle mismatch"','pass'),
   ("capidx_not_rebuilt",E,"                self.capidx[r] = 0\n","                pass\n"),
   ("investigate_first",E,"            if score > score_b:","            if score > score_b or best is None and score:"),
   ("correct_keeps_old",E,"        self.facts[k] = []\n","        pass\n"),
   ("journal_not_replayed",S,"            if jp.exists():","            if False:"),
]
res=[]
for name,f,a,b in M:
    src=f.read_text(); assert a in src, name
    f.write_text(src.replace(a,b,1))
    try:
        p=subprocess.run([sys.executable,'-m','packetlm.hdc.test_hdc'],cwd='/tmp/v69/mutclone',capture_output=True,text=True,timeout=120)
        killed=p.returncode!=0
    except subprocess.TimeoutExpired:
        killed=True
    finally:
        f.write_text(src)
    res.append((name,killed)); print(name,'killed' if killed else 'SURVIVED',flush=True)
print(sum(k for _,k in res),'/',len(res))
