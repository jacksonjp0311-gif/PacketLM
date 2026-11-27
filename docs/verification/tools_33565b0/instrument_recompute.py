"""Verifier: every primary and secondary contrast of docs/evidence/g58/g58_receipt.json recomputed with
the pinned instrument (70297af, clean) on the CSVs in DIR; the first report line is compared with the
receipt's. Usage: instrument_recompute.py [DIR] [RECEIPT]"""
import json, subprocess, sys
D = sys.argv[1] if len(sys.argv) > 1 else "docs/evidence/g58"
RC = sys.argv[2] if len(sys.argv) > 2 else "docs/evidence/g58/g58_receipt.json"
I = "/workspace/vendor/learning-amortization"
head = subprocess.run(["git", "-C", I, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
dirty = subprocess.run(["git", "-C", I, "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
print(json.dumps({"instrument_head": head, "dirty": dirty}))
rc = json.load(open(RC)); ok = n = 0
for cur, c in rc["curricula"].items():
    for kind in ("primary", "secondary"):
        for x in c[kind]:
            p = subprocess.run([sys.executable, "-m", "amortization", f"{D}/{cur}_total.csv", "--cont", x["cont"], "--base", x["base"],
                                "--n", str(x["n"]), "--bootstrap", "5000"], capture_output=True, text=True, env={"PYTHONPATH": I, "PATH": "/usr/bin:/bin"})
            mine = (p.stdout.strip().splitlines() or [""])[0]; theirs = x["report"].splitlines()[0] if x["report"] else ""
            n += 1; ok += mine == theirs
            print(json.dumps({"cur": cur, "kind": kind, "cont": x["cont"], "base": x["base"], "match": mine == theirs, "mine": mine, "receipt": theirs}))
print(json.dumps({"contrasts": n, "matching": ok}))
