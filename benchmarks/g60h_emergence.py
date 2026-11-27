"""G60H emergence log line (docs/G60H.md §9), fields as benchmarks/g59_emergence.py, from receipts only.
Run: python3 benchmarks/g60h_emergence.py <gate_m1> <gate_m2> <scale> <commit> [notes]"""
from __future__ import annotations
import json
import sys


def line(gate, gate2, scale, commit, notes=""):
    C = gate["curricula"]
    cur = list(C)
    an = {c: C[c]["analyses"] for c in cur}
    P = lambda g, c, k: g["curricula"][c]["analyses"]["parsed"][k]["A"]  # noqa: E731
    return {"milestone": "G60H", "commit": commit,
            "seeds": {c: f"{min(v)}-{max(v)}" for c, v in gate["seeds"].items()} | {"part_S": f"{min(scale['seeds'])}-{max(scale['seeds'])}"},
            "protocol_id": "g58-serve protocol with packetlm.hdc.serve + g60h_scale (1 worker; work = function calls)",
            "representation": "sparse block codes K=32 x L=64 (D=2048), bind = blockwise add mod L, rho = block shift, OR bundles, cleanup",
            "work": {c: {"lines_C/B": an[c]["emergence"]["lines_C/B"]} for c in cur},
            "cpu": {c: {"A(Ch+maint||Bh)": P(gate, c, "Ch+maint||Bh"), "A(Ch+maint||Ph+maint)": P(gate, c, "Ch+maint||Ph+maint"),
                        "decomposition": {k: v["A"] for k, v in an[c]["parsed"].items()},
                        "maintenance_share": an[c]["maintenance_share"],
                        "per_op_cost_ratio_vs_B": {w: an[c]["work_split"][w]["vs_B"]["rho"] for w in an[c]["work_split"]},
                        "A_work_vs_B": {w: an[c]["work_split"][w]["vs_B"]["A_work"] for w in an[c]["work_split"]},
                        "margin2_A(Ch+maint||Bh)": P(gate2, c, "Ch+maint||Bh"),
                        "margin2_A(Ch+maint||Ph+maint)": P(gate2, c, "Ch+maint||Ph+maint")} for c in cur},
            "scaling": {a: {k: v for k, v in scale["summary"][a].items() if k.startswith(("alpha_", "R0_", "mean_task", "snapshot_cpu"))}
                        for a in scale["summary"]},
            "scaling_verdicts": {k: scale.get(k) for k in ("bounded_hC", "bounded_charged_hC")} | {"workers": scale.get("workers")},
            "strata": {c: an[c]["strata_B_depth"] for c in cur},
            "strata_margin2": {c: gate2["curricula"][c]["analyses"]["strata_B_depth"] for c in cur},
            "in_run": {c: an[c]["in_run"] for c in cur},
            "outcomes": {c: C[c]["outcomes"] for c in cur},
            "censoring": {c: an[c]["censoring"] for c in cur},
            "reuse": {c: an[c]["emergence"]["reuse"] for c in cur},
            "depth": {c: an[c]["emergence"]["depth"] for c in cur},
            "cascades": {c: an[c]["emergence"]["cascades"] for c in cur},
            "retention": {c: an[c]["emergence"]["retention"] for c in cur},
            "transfer_unrel_lib_uses": C["unrel"]["outcomes"]["Ch"]["uses_library"],
            "rate_ratio": {c: an[c]["rate_ratio"] for c in cur},
            "gate": {k: v for k, v in gate["gate"].items() if k != "Q2_detail"},
            "gate_margin2": {k: v for k, v in gate2["gate"].items() if k != "Q2_detail"},
            "notes": notes}


if __name__ == "__main__":
    g, g2, s = (json.load(open(x)) for x in sys.argv[1:4])
    print(json.dumps(line(g, g2, s, sys.argv[4], sys.argv[5] if len(sys.argv) > 5 else "")))
