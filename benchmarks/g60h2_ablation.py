"""G60H2 ablation analysis (docs/G60H2.md §6c, verifier M1): HDC engine (config e) vs the same engine
with plain exact data structures (config p), same seeds. Per curriculum: reply streams identical per
run (guard), and A(HDC||plain) = 1 - C_HDC / C_plain by the pinned instrument for each role
(C+maint, B, P+maint; negative = the hypervector representation costs more).
Run: python3 benchmarks/g60h2_ablation.py <e_artifact_dir> <p_artifact_dir> <out.json>"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))
import g59_analysis as G  # noqa: E402
from la_export import export  # noqa: E402
from g51 import instrument  # noqa: E402


def main(argv):
    de, dp, out = Path(argv[0]), Path(argv[1]), Path(argv[2])
    rep = {}
    for f in sorted(de.glob("*_raw.json")):
        c = f.name[:-9]
        g = dp / f.name
        if not g.exists():
            continue
        re_, rp = json.loads(f.read_text()), json.loads(g.read_text())
        seeds = sorted({k.split(":")[0] for k in re_})
        same = all(re_[f"{s}:{r}e"]["reply_stream_sha256"] == rp[f"{s}:{r}p"]["reply_stream_sha256"] for s in seeds for r in "CBP")
        raw = {**re_, **rp}
        csv = out.parent / f"ablation_{c}_cpu.csv"
        export(raw, csv, None, "cpu_total_s")
        n = len(re_[f"{seeds[0]}:Ce"]["tasks"])
        pairs = [("Ce+maint", "Cp+maint"), ("Be", "Bp"), ("Pe+maint", "Pp+maint")]
        res = [instrument(csv, a, b, n) for a, b in pairs]
        rep[c] = {"replies_identical": same,
                  "cpu_total": {a: round(sum(raw[f"{s}:{a}"]["cpu_total_all_s"] for s in seeds), 3) for a in ("Ce", "Cp", "Be", "Bp", "Pe", "Pp")},
                  "A_hdc_vs_plain": {f"{x['cont']}||{x['base']}": G.parse(x["report"])["A"] if x["report"] else x["err"] for x in res}}
    out.write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
