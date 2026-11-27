"""Verifier mutations for the restated G45 t5 (retention). Each one is applied to a temporary
copy of the repository; run_seed is run on 101/202/303 and the restated check must fail."""
import sys, shutil, subprocess, json, os, tempfile
SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")) if len(sys.argv) < 2 else sys.argv[1]
SAY = 'return text + (" [provisional]" if got.get("provisional") else "")'
FLUSH = '''                self.stats["grown_requalified"] = self.stats.get("grown_requalified", 0) + 1
                self.acquire(n)'''
MUTS = {
 "t5_value_changed_when_provisional": (SAY, 'return (text.replace(str(got["value"]), str(got["value"])[::-1]) + " [provisional]") if got.get("provisional") else text'),
 "t5_value_lost_when_provisional": (SAY, 'return "unknown" if got.get("provisional") else text'),
 "t5_demoted_without_rescan": (FLUSH, '''                self.stats["grown_requalified"] = self.stats.get("grown_requalified", 0) + 1
                self._set_status(n, ver["v"], "provisional", "requalified")'''),
 "t5_rescan_adopts_blocker": (FLUSH, FLUSH + '''
                _b = self.state["hypotheses"].get(n, {}).get("blocking") or []
                if _b:
                    self.version(n)["seq"] = list(_b[-1])'''),
 "t5_value_changed_qualified": (SAY, 'return text.replace(str(got["value"]), str(got["value"])[::-1]) if (not got.get("provisional") and self.state["turn"] > 590) else text + (" [provisional]" if got.get("provisional") else "")'),
}
RUN = '''
import sys, json, pathlib, tempfile
sys.path.insert(0, ".")
from packetlm import g45_test
res = {}
for seed in (101, 202, 303):
    r = g45_test.run_seed(seed, pathlib.Path(tempfile.mkdtemp()))
    res[seed] = [r["retention_identical"], r["retention_strict_identical"], r["retention_demoted"], r["domains"][0]["eval"]["wrong"]]
print(json.dumps(res))
'''
for name, (old, new) in MUTS.items():
    d = tempfile.mkdtemp()
    shutil.copytree(os.path.join(SRC, "packetlm"), os.path.join(d, "packetlm"))
    p = os.path.join(d, "packetlm", "engine.py")
    s = open(p).read()
    assert s.count(old) == 1, name
    open(p, "w").write(s.replace(old, new))
    out = subprocess.run([sys.executable, "-c", RUN], cwd=d, capture_output=True, text=True)
    res = json.loads(out.stdout) if out.returncode == 0 else {"error": out.stderr[-300:]}
    killed = out.returncode != 0 or all(not v[0] for v in res.values())
    print(name, "KILLED" if killed else "SURVIVED", json.dumps(res))
