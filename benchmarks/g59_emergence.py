"""G59 emergence log line (docs/G59.md §9; format of docs/invariants/INVARIANTS.md §2, branch
invariants-analysis): every field derived from the registered receipts, no engine runs.
Run: python3 benchmarks/g59_emergence.py <gate_receipt.json> <scale_receipt.json> <commit> [notes]
Prints one JSON line (append it to docs/invariants/emergence_log.jsonl)."""
from __future__ import annotations
import json
import sys


def line(gate, scale, commit, notes=""):
    C = gate["curricula"]
    cur = list(C)
    an = {c: C[c]["analyses"] for c in cur}
    P = lambda c, k: an[c]["parsed"][k]["A"]  # noqa: E731
    ks = scale["summary"].get("k", {})
    out = {"milestone": "G59", "commit": commit,
           "seeds": {c: f"{min(v)}-{max(v)}" for c, v in gate["seeds"].items()} | {"part_S": f"{min(scale['seeds'])}-{max(scale['seeds'])}"},
           "protocol_id": "g58-serve + g59_scale (charged maintenance, work = function calls)",
           "work": {c: {"evaluations_C/P": an[c]["emergence"].get("evaluations_C/P"),
                        "executions_C/P": an[c]["emergence"].get("executions_C/P"),
                        "lines_C/B": an[c]["emergence"]["lines_C/B"],
                        "lines_C/B_excl_probes": an[c]["emergence"]["lines_C/B_tasks_only"]} for c in cur},
           "cpu": {c: {"A(Ck+maint||Bk)": P(c, "Ck+maint||Bk"), "A(Ck+maint||Pk+maint)": P(c, "Ck+maint||Pk+maint"),
                       "A(Ck+maint||Cr+maint)": P(c, "Ck+maint||Cr+maint"),
                       "per_op_cost_ratio_vs_B": {w: an[c]["work_split"][w]["vs_B"]["rho"] for w in an[c]["work_split"]},
                       "A_work_vs_B": {w: an[c]["work_split"][w]["vs_B"]["A_work"] for w in an[c]["work_split"]}} for c in cur},
           "scaling": {a: {k: v for k, v in scale["summary"][a].items() if k.startswith(("alpha_", "R0_", "R1k_", "mean_task", "snapshot_cpu"))}
                       for a in scale["summary"]},
           "scaling_verdicts": {k: scale.get(k) for k in ("bounded_k", "bounded_charged_k", "bounded_work_k", "material_k_vs_ref")},
           "strata": {c: an[c]["strata_B_depth"] for c in cur},
           "in_run": {c: an[c]["in_run"] for c in cur},
           "outcomes": {c: C[c]["outcomes"] for c in cur},
           "censoring": {c: an[c]["censoring"] for c in cur},
           "reuse": {c: an[c]["emergence"]["reuse"] for c in cur},
           "depth": {c: an[c]["emergence"]["depth"] for c in cur},
           "cascades": {c: an[c]["emergence"]["cascades"] for c in cur},
           "retention": {c: an[c]["emergence"]["retention"] for c in cur},
           "transfer_unrel_lib_uses": C["unrel"]["outcomes"]["Ck"]["uses_library"] if "unrel" in C else None,
           "rate_ratio": {c: an[c]["rate_ratio"] for c in cur},
           "gate": {k: v for k, v in gate["gate"].items() if k != "Q2_detail"},
           "notes": notes}
    return out


if __name__ == "__main__":
    g, s = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
    print(json.dumps(line(g, s, sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "")))
