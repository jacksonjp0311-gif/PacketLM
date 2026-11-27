"""G60H2 mutation runner (moved into the repo, verifier L2 of verify-69b5b26). Each mutation edits one
source string in a temporary copy of packetlm/ and runs the HDC checks there (the working tree is never
edited); a mutation is killed iff the checks fail (or time out). Equivalent mutations are listed with the
reason and still run. Run: python3 benchmarks/g60h2_mutations.py [--out file.json]"""
from __future__ import annotations
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
E, S, P = "packetlm/hdc/engine.py", "packetlm/hdc/serve.py", "packetlm/hdc/plain.py"
M = [  # (name, file, old, new)  -- G60H's twelve (strings updated to the G60H2 source)
    ("library_ignored", E, "        if self.library if lib is None else lib:\n            caps = set()\n            for r in out:\n                F =",
     "        if True:\n            caps = set()\n            for r in out:\n                F ="),
    ("no_blocking", E, 'status = "provisional" if blockers else "qualified"', 'status = "qualified"'),
    ("no_prune", E, "                    if any(not t2[i] for i in vi):", "                    if False:"),
    ("no_dedupe", E, "                    if t2 in seen:\n                        continue", "                    pass"),
    ("domain_ignored", E, 'prov = ver["status"] == "provisional" or s not in ver["domain"]', 'prov = ver["status"] == "provisional"'),
    ("decode_unchecked", E, "        if dec != exact:", "        if False:"),
    ("touched_check_off", E, 'assert C.unbind(k, C.rho(self.prim.code[r])) == self.ent.code[s], "fact key does not unbind to its subject"\n            assert all(v in self.ent.name for v in self.facts[k]), "fact value without a clean code"', "pass"),
    ("full_check_off", E, 'assert all(self.sig.get(s) == v for s, v in sig.items()), "signature bundle mismatch"', "pass"),
    ("capidx_not_rebuilt", E, "                self.capidx[r] = 0\n", "                pass\n"),
    ("investigate_first", E, "            if score > score_b:", "            if score > score_b or best is None and score:"),
    ("correct_keeps_old", E, "        vals[:] = []\n", "        pass\n"),
    ("journal_not_replayed", S, "            if jp.exists():", "            if False:"),
    # verifier's (tools_69b5b26/mut_extra.py)
    ("ambiguity_ignored", E, '        if len(groups) > 1:\n            self._cap_provisional(name)\n            return {"result": "ambiguous"}',
     "        if False:\n            pass"),
    ("margin_ignored_dp", E, "                if n >= found + margin:\n                    break", "                break"),
    ("self_not_excluded", E, "            caps.discard(exclude)\n", "            pass\n"),
    ("omega_empty", E, "        return X + om, len(X)", "        return X, len(X)"),
    ("several_unchecked", E, "                    if len(S) < 2:\n                        return False", "                    pass"),
    # G60H2
    ("margin_ignored_mitm", E, "                if n >= found + self.margin:\n                    break", "                break"),
    ("equal_check_skipped", E, "            prop = self._search(name, True, None)\n            res = self._certify(name)",
     "            prop = self._search(name, True, None)\n            res = self._search(name, True, self.margin)"),
    ("library_form_always", E, "            if len(pg) == 1 and pg[0][0] == t:", "            if pg:"),
    ("mitm_no_prune", E, "                    if any(not pj2[j] for j in vpos):", "                    if False:"),
    ("mitm_seen_ignored", E, "for t, q in got.items() if t not in seen)", "for t, q in got.items() if True)"),
    ("mitm_not_lexmin", E, "if t not in best or seq < best[t]:", "if True:"),
    ("mitm_suffix_truncated", E, "                    for r in sorted(rs):", "                    for r in sorted(rs)[:1]:"),
    ("inverse_not_written", E, "            iv.append(self.ent.code[s])\n", "            pass\n"),
    ("pcache_kept_on_tell", E, "        if s in self.ent.code:\n            self.pcache.clear()", "        if False:\n            self.pcache.clear()"),
    ("collision_not_counted", E, '                self.counters["collisions"] += 1', "                pass"),
    ("collision_no_spill", E, "        if own != (s, r):\n            if (s, r) not in self.spill:", "        if False:\n            if (s, r) not in self.spill:"),
    ("code_collision_unchecked", E, '        if self.ent.collided and (c in self.ent.collided or any(v in self.ent.collided for v in vals)):\n            self.counters["code_collision_reads"] += 1  # value',
     '        if False:\n            self.counters["code_collision_reads"] += 1  # value'),
    ("signature_unchecked", E, "        if g == exact:\n            return got", "        if True:\n            return got"),
    ("capidx_unchecked", E, "        return exact\n\n    def _reindex", "        return got\n\n    def _reindex"),
    ("plain_no_inverse", P, "            self.inv.setdefault((o, r), []).append(s)\n", "            pass\n"),
    ("plain_no_library", P, "        if self.library if lib is None else lib:", "        if False:"),
]
EQUIVALENT = {"investigate_first": "the extra clause only fires when score <= score_b = 0 with score > 0, impossible"}


def main(argv):
    res = []
    with tempfile.TemporaryDirectory() as d:
        for name, f, a, b in M:
            w = Path(d) / name
            shutil.copytree(ROOT / "packetlm", w / "packetlm", ignore=shutil.ignore_patterns("__pycache__"))
            src = (w / f).read_text()
            assert src.count(a) == 1, (name, src.count(a))
            (w / f).write_text(src.replace(a, b, 1))
            try:
                p = subprocess.run([sys.executable, "-m", "packetlm.hdc.test_hdc"], cwd=w, capture_output=True, text=True, timeout=300)
                killed, why = p.returncode != 0, [ln for ln in p.stdout.splitlines() if ln.startswith("FAIL")][:3]
            except subprocess.TimeoutExpired:
                killed, why = True, ["timeout"]
            res.append({"name": name, "file": f, "killed": killed, "failing_checks": why, "equivalent": EQUIVALENT.get(name)})
            print(name, "killed" if killed else "SURVIVED", flush=True)
    out = {"total": len(res), "killed": sum(r["killed"] for r in res),
           "survived": [r["name"] for r in res if not r["killed"]], "runs": res}
    if "--out" in argv:
        Path(argv[argv.index("--out") + 1]).write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("total", "killed", "survived")}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
