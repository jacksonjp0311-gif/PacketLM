"""Verifier: totals over routed_diff logs (first JSON line of each) and the bad-case lines."""
import json, glob, sys
keys = ["sessions", "calls", "readonly_calls", "crashes", "torn", "drops", "deep_checks", "errors", "reply_diffs", "state_diffs",
        "deep_diffs", "final_bytes_diffs", "journal_diffs", "audit_violations"]
T = {k: 0 for k in keys}
for f in sorted(glob.glob(sys.argv[1] if len(sys.argv) > 1 else "logs/adv/r*.log")):
    lines = open(f).read().splitlines()
    if not lines:
        print(f, "EMPTY"); continue
    d = json.loads(lines[0])
    print(f.split("/")[-1], {k: d.get(k, 0) for k in keys}, "K", d["K"], "lib", d["lib"], "audit", d["audit"], "extra-lines", len(lines) - 1)
    for k in keys:
        T[k] += d.get(k, 0)
print("TOTAL", T)
