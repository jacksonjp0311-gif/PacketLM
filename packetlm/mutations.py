"""Mutation run: break one engine mechanism at a time and confirm a check fails.

Copies the repo to a temp dir, applies one textual mutation to engine.py,
runs `python -m packetlm.g44_test` there, and records which checks failed.
A mutation that no check notices is reported as SURVIVED.
"""

from __future__ import annotations
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MUTATIONS = {
    "judge_none_contradicts": ('    if pred is None:\n        return "undetermined"', '    if pred is None:\n        return "contradicted"'),
    "blocking_ignored": ('status = "provisional" if blocking else "qualified"', 'status = "qualified"'),
    "review_noop": ('            if h["status"] == "contradicted":\n                events += self._set_status(name, ver["v"], "suspended"',
                    '            if False:\n                events += self._set_status(name, ver["v"], "suspended"'),
    "superseded_not_pinned": ('PINNED_OK = EXEC_OK + ("superseded",)', 'PINNED_OK = EXEC_OK'),
    "cycle_offered": ('                    continue  # would create a cycle', '                    pass'),
    "first_proof_only": ('        for p in paths:\n            self.tell(', '        for p in paths[:1]:\n            self.tell('),
    "tms_all_or_nothing": ('                    if not keep:\n                        removed.add', '                    if True:\n                        removed.add'),
    "expression_borrows": ('meaning = (cap or {}).get("express") or rel',
                           'meaning = (cap or {}).get("express") or next((c["meaning"] for c in self.state["library"] if c.get("kind", "svo") == "svo"), rel)'),
    "no_dangling_check": ('_need(p in ids, f"dangling premise', '_need(True or p in ids, f"dangling premise'),
    "no_backup_fallback": ('for label, p in (("primary", path), ("backup", bak)):', 'for label, p in (("primary", path),):'),
    "ambiguity_off": ('        if len(found) > 1:\n            return {"status": "ambiguous"', '        if False:\n            return {"status": "ambiguous"'),
    "library_off": ('        if self.use_library:\n            for n in sorted', '        if False:\n            for n in sorted'),
    "zero_support_dropped": ('                else:\n                    out.append(h)', '                elif h["support"]:\n                    out.append(h)'),
    "unanswered_lost": ('        if prior.get("unanswered"):', '        if False:'),
    "compose_keeps_source": ('            row = g.compose([row], idx["rows"][rel])[0]', '            row = row | g.compose([row], idx["rows"][rel])[0]'),
}


def run() -> dict:
    results = {}
    for name, (old, new) in MUTATIONS.items():
        with tempfile.TemporaryDirectory() as d:
            dst = Path(d) / "repo"
            shutil.copytree(ROOT / "packetlm", dst / "packetlm", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT / "data", dst / "data")
            eng = dst / "packetlm" / "engine.py"
            src = eng.read_text()
            if src.count(old) != 1:
                results[name] = {"error": "mutation site not found exactly once"}
                continue
            eng.write_text(src.replace(old, new))
            p = subprocess.run([sys.executable, "-m", "packetlm.g44_test"], cwd=dst, capture_output=True, text=True, timeout=600)
            rec = dst / "artifacts" / "g44_receipt.json"
            failed = json.loads(rec.read_text())["failed"] if rec.exists() and p.returncode else []
            results[name] = {"exit": p.returncode, "failed": failed,
                             "verdict": "KILLED" if p.returncode else "SURVIVED",
                             "crash": p.stderr.strip().splitlines()[-1][:200] if p.returncode and not failed else None}
    out = {"mutations": results, "killed": sum(r.get("verdict") == "KILLED" for r in results.values()),
           "total": len(results)}
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/mutations_receipt.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    r = run()
    raise SystemExit(0 if r["killed"] == r["total"] else 1)
