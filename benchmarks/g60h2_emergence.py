"""G60H2 emergence log line (docs/G60H2.md §9), from the registered receipts only.
Run: python3 benchmarks/g60h2_emergence.py <commit>  (reads artifacts/g60h2_reg*)"""
from __future__ import annotations
import json
import sys
from pathlib import Path

A = Path(__file__).resolve().parent.parent / "artifacts"


def rc(n):
    return json.loads((A / n / f"{n}_receipt.json").read_text())


def main(commit):
    e1, e2, p1, de, do = rc("g60h2_reg_e1"), rc("g60h2_reg_e2"), rc("g60h2_reg_p1"), rc("g60h2_reg_decoy_e"), rc("g60h2_reg_decoy_o")
    sc = rc("g60h2_reg_scale")
    abl = json.loads((A / "g60h2_reg" / "ablation.json").read_text())
    cur = list(e1["curricula"])
    out = {"milestone": "G60H2", "commit": commit,
           "seeds": {c: f"{min(v)}-{max(v)}" for c, v in e1["seeds"].items()} | {"decoy": "561-567", "part_S": "551-557"},
           "protocol_id": "g58-serve protocol with packetlm.hdc.serve; C --check=equal, all arms --certifier=mitm; g60h_scale --config e (1 worker)",
           "rule": "C's verdict = B's base-language uniqueness rule on the same evidence (margin m), fully charged; library proposes only",
           "gate": {m: {"verdict": g["gate"]["verdict"], "A(Ce+maint||Be)": g["gate"]["A"], "library_term": g["gate"]["library_term"],
                        "P||B": {c: g["curricula"][c]["analyses"]["parsed"]["Pe||Be"]["A"] for c in cur},
                        "strata_comp": g["gate"]["strata_comp"],
                        "long": {"A(Ce||Be)": g["gate"]["accumulation"]["A"], "beta": g["gate"]["accumulation"]["beta"],
                                 "o/s_pooled": g["gate"]["accumulation"]["rate_ratio"].get("rate_ratio_o_over_s"),
                                 "o/s_per_seed": {s: v.get("rate_ratio_o_over_s") for s, v in g["gate"]["accumulation"]["rate_ratio_per_seed"].items()}}}
                    for m, g in (("margin1", e1), ("margin2", e2))},
           "proposal": {c: {k: e1["curricula"][c]["counters"]["Ce"].get("cum_" + k, 0) for k in ("cert_runs", "prop_agree", "prop_differ", "prop_none")} for c in cur},
           "counters_error_total": sum(v for g in (e1, e2, p1, de, do) for c in g["curricula"].values() for arm in c["counters"].values()
                                       for k, v in arm.items() if any(t in k for t in ("error", "collision", "spurious", "missing"))),
           "ablation_hdc_vs_plain": {c: {"replies_identical": v["replies_identical"], **v["A_hdc_vs_plain"]} for c, v in abl.items()},
           "plain_gate": {"verdict": p1["gate"]["verdict"], "A": p1["gate"]["A"], "library_term": p1["gate"]["library_term"]},
           "decoy": {"equal_check": de["curricula"]["decoy"]["outcomes"]["Ce"] | {}, "own_rule": do["curricula"]["decoy"]["outcomes"]["Co"] | {}},
           "part_S": {a: {"alpha_task_16k_64k": sc["summary"][a]["alpha_16000_64000"][:2], "alpha_work": sc["summary"][a]["alpha_work_16000_64000"][:2],
                          "task_ms": sc["summary"][a]["mean_task_cpu_ms"]} for a in ("hC", "hP")},
           "observations": []}
    for k in ("equal_check", "own_rule"):
        out["decoy"][k] = {x: out["decoy"][k].get(x) for x in ("sealed_correct", "wrong_qualified_sealed", "transfer_wrong_qualified", "retention_changed")}
    return out


if __name__ == "__main__":
    o = main(sys.argv[1])
    o["observations"] = sys.argv[2:]
    print(json.dumps(o))
