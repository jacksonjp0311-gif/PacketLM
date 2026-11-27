import sys, json, pathlib
sys.path.insert(0, "/workspace/pl-verify")
from packetlm import g45_test
out = pathlib.Path("/workspace/pl-verify-logs/v6/t5")
for seed in (101, 202, 303):
    r = g45_test.run_seed(seed, out)
    r.pop("sessions")
    json.dump(r, open(out / f"r{seed}.json", "w"), indent=1, default=str)
    print(seed, r["retention_identical"], r["retention_strict_identical"], r["retention_demoted"])
