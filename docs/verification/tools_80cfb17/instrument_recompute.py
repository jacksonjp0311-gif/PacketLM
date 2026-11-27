"""Verifier (verify-80cfb17): every primary, secondary and resource contrast of docs/evidence/g59/g59_receipt.json
recomputed with the pinned instrument (70297af, clean) on the registered CSVs; first report line compared.
Extra (not in the receipt): Pk+maint||Bk (accumulated-state cost without the library) and Ck+maint||Pk... already;
plus Cr+maint||Br per curriculum. Usage: instrument_recompute.py"""
import json, subprocess, sys
D = "docs/evidence/g59"; I = "/workspace/vendor/learning-amortization"
run = lambda *a: subprocess.run(a, capture_output=True, text=True).stdout.strip()
print(json.dumps({"instrument_head": run("git", "-C", I, "rev-parse", "--short", "HEAD"), "dirty": run("git", "-C", I, "status", "--porcelain")}))
rc = json.load(open(f"{D}/g59_receipt.json")); ok = n = 0
def inst(csv, a, b, nn):
    p = subprocess.run([sys.executable, "-m", "amortization", csv, "--cont", a, "--base", b, "--n", str(nn), "--bootstrap", "5000"],
                       capture_output=True, text=True, env={"PYTHONPATH": I, "PATH": "/usr/bin:/bin"})
    return p.stdout.strip()
for cur, c in rc["curricula"].items():
    an = c["analyses"]
    jobs = [("cpu_total_s", x) for k in ("primary", "secondary") for x in an[k]] + [(res, x) for res, xs in an["resources"].items() for x in xs]
    for res, x in jobs:
        mine = (inst(f"{D}/{cur}_{res}.csv", x["cont"], x["base"], x["n"]).splitlines() or [""])[0]
        theirs = x["report"].splitlines()[0] if x.get("report") else ""
        n += 1; ok += mine == theirs
        if mine != theirs: print(json.dumps({"cur": cur, "res": res, "cont": x["cont"], "base": x["base"], "mine": mine, "receipt": theirs}))
    for a, b in (("Pk+maint", "Bk"), ("Cr+maint", "Br"), ("Ck", "Bk")):
        print(json.dumps({"cur": cur, "extra": f"{a}||{b}", "report": inst(f"{D}/{cur}_cpu_total_s.csv", a, b, c["n"]).splitlines()[:2]}))
print(json.dumps({"contrasts": n, "matching": ok}))
