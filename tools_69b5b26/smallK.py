"""Spot check (untimed): run gate jobs with small codes (env K, L) and compare reply streams with the registered run;
report the in-run capability decode counters (via the g60h_decode_audit hook)."""
import os, sys, json, gzip
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "benchmarks"), str(ROOT)]
import g56, g60h_decode_audit as A
for r_ in g56.BASEF:
    g56.BASEF[r_] = g56.BASEF[r_] + ["--margin=1"]
out = []
for K, L in [(32, 64), (16, 16), (8, 16), (8, 64), (4, 64)]:
    os.environ["PACKETLM_HDC_K"], os.environ["PACKETLM_HDC_L"] = str(K), str(L)
    for cur, seed in [("comp", 401), ("long", 441)]:
        raw = json.load(gzip.open(ROOT / f"docs/evidence/g60h/gate_m1/{cur}_raw.json.gz"))
        try:
            r = A.job((cur, seed, "Ch", f"/tmp/v69/smallK_{K}_{L}"))
            same = r["reply_stream_sha256"] == raw[f"{seed}:Ch"]["reply_stream_sha256"]
            rec = {"K": K, "L": L, "cur": cur, "seed": seed, "same_replies": same, **{k: v for k, v in r["counters"].items()}}
        except Exception as e:
            rec = {"K": K, "L": L, "cur": cur, "seed": seed, "error": str(e)[:200]}
        print(json.dumps(rec), flush=True); out.append(rec)
Path(ROOT / "tools_69b5b26/out/smallK.json").write_text(json.dumps(out, indent=1))
