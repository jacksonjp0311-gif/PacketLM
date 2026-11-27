"""Mutation run: break one engine mechanism at a time and confirm a check fails.

Copies the repo to a temp dir, applies one textual mutation to engine.py (or the named module),
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
    "blocking_ignored": ('        status = "provisional" if blocking else "qualified"\n        record["candidate"]', '        status = "qualified"\n        record["candidate"]'),
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
    "activation_overprunes": ('                if not nxt:\n                    pruned +=', '                if not nxt or p == prims[0]:\n                    pruned +='),
    "open_world_off": ('                        if conflict or (support >= 1', '                        if (support >= 1'),
    "prune_on_evidence_only": ('        level, seen = [([], [{e} for e in D], ())], {()}', '        level, seen = [([], [{e} if e in dict(obs) else set() for e in D], ())], {()}'),
    "domain_too_narrow": ('            if v is None and e not in dom:\n                continue', '            if e not in dom:\n                continue'),
    "dedupe_by_last_step": ('                    key = bseq + tuple(pb)', '                    key = tuple(pb)'),
    "binding_trusted_on_load": ('        if v2:\n            pkt = bind(', '        if False:\n            pkt = bind('),
    "v3_accepts_packets": ('            _need("bits" not in f and "count" not in f,', '            _need(True,'),
    "migration_silent": ('                report["migrated"] = f"', '                _silent = f"'),
    "packet_roles_swapped": ('[bits_for(f["s"], 0) ^ bits_for(f["r"], 1) ^ bits_for(f["o"], 2)', '[bits_for(f["o"], 0) ^ bits_for(f["r"], 1) ^ bits_for(f["s"], 2)'),
    "primary_trusted_on_save": ('                if hashlib.sha256(cur).hexdigest() != self._known_bytes:', '                if False:'),
    "restore_off": ('                {self._archived_tok[t] for t in toks if t in self._archived_tok}', '                set()'),
    "gate_ignores_recent": ('        if n < MIN_AGE or any(c > call - GUARD for r in recs for c in r[1:]):', '        if n < MIN_AGE:', "retention.py"),
    "archive_deleted_on_restore": ('    state["facts"].extend(comp["facts"])', '    f.unlink()\n    state["facts"].extend(comp["facts"])', "retention.py"),
    "prog_union_clauses": ('        if cur:\n            out = frozenset(cur)\n            break', '        if cur:\n            out = out | frozenset(cur)', "programs.py"),
    "prog_not_inverted": ('                cur = {y for y in cur if not ctx.has(y, q, t)}', '                cur = {y for y in cur if ctx.has(y, q, t)}', "programs.py"),
    "prog_no_recursion": ('                if depth + 1 <= MAX_DEPTH:\n                    for y in cur:', '                if depth + 1 <= 1:\n                    for y in cur:', "programs.py"),
    "prog_deps_hidden": ('            out += progs.deps(s)  # capabilities used inside', '            pass  # capabilities used inside'),
    "prog_investigate_defined_only": ('                if not known or len(set(allp)) < 2:', '                if len(set(known)) < 2:'),
    "prog_scan_ignored": ('        status = "qualified" if complete and not blockers else "provisional"', '        status = "qualified"'),
    "prog_order_dependent_ties": ('        for e in (sorted(self.entities()) if self.programs else self.entities()):', '        for e in self.entities():'),
    "static_ignores_archive": ('        if ret and retention == "static" and ret["archived"]:', '        if False:'),
    "no_requalify": ('        out["review"] = retired + self.review() + self._requalify_retired()\n        return out\n\n    def correct_example', '        out["review"] = retired + self.review()\n        return out\n\n    def correct_example'),
    "scan_short_horizon": ('        horizon = self.deepen if (max_len is None and self.deepen) else searched', '        horizon = searched'),
    "deepen_past_ambiguity": ('                if any(h["status"] == "supported" for h in live):', '                if sum(h["status"] == "supported" for h in live) == 1:'),
    "compose_skips_bit": ('            acc |= b_rows[low.bit_length() - 1]\n            row ^= low', '            acc |= b_rows[low.bit_length() - 1]\n            row ^= low\n            row &= row - 1', "geom.py"),
    "compose_keeps_source": ('            return g.compose([row], self._rows(token))[0]', '            return row | g.compose([row], self._rows(token))[0]'),
}


def run() -> dict:
    results = {}
    for name, (old, new, *target) in MUTATIONS.items():
        with tempfile.TemporaryDirectory() as d:
            dst = Path(d) / "repo"
            shutil.copytree(ROOT / "packetlm", dst / "packetlm", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT / "data", dst / "data")
            eng = dst / "packetlm" / (target[0] if target else "engine.py")
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
