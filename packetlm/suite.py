"""Run the whole suite in fresh processes and count named checks.

Suite: the eight workflow modules plus G44. Each must exit 0 and list no failures.
Smoke: modules with no assertions; they only have to run.
"""

from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

SUITE = ["g37_test", "system", "bridge", "roles", "runtime", "chat", "qualify", "geom", "g44_test", "legacy_checks", "g45_test"]
SMOKE = ["crossdomain", "demo", "feedoffer", "gap", "gaptest", "learn", "memory", "nexttoken", "train", "vocab"]
RECEIPT = {"g37_test": "g37_receipt.json", "g44_test": "g44_receipt.json", "legacy_checks": "legacy_receipt.json", "g45_test": "g45_receipt.json"}


def count(name) -> tuple[int, int]:
    data = json.loads(Path("artifacts", RECEIPT.get(name, f"{name}_receipt.json")).read_text())
    if name in ("g44_test", "g45_test"):
        return data["count"], len(data["failed"])
    if name == "g37_test":
        return len(data["tests"]), len(data["failed"])
    n = sum(1 for v in data.values() if isinstance(v, bool))
    return n, len(data["failed"])


def main() -> int:
    rows, total, failed = [], 0, 0
    for name in SUITE:
        rc = subprocess.run([sys.executable, "-m", f"packetlm.{name}"], capture_output=True, timeout=600).returncode
        n, f = count(name) if rc == 0 or Path("artifacts").exists() else (0, 0)
        rows.append({"module": name, "exit": rc, "checks": n, "failed": f})
        total += n
        failed += f + (1 if rc and not f else 0)
    smoke = []
    for name in SMOKE:
        rc = subprocess.run([sys.executable, "-m", f"packetlm.{name}"], capture_output=True, timeout=600).returncode
        smoke.append({"module": name, "exit": rc})
    out = {"suite": rows, "checks": total, "failed": failed,
           "modules_passed": sum(r["exit"] == 0 for r in rows), "modules": len(rows),
           "smoke_ran": sum(s["exit"] == 0 for s in smoke), "smoke": len(smoke), "smoke_detail": smoke}
    print(json.dumps(out, indent=2))
    return 0 if failed == 0 and all(r["exit"] == 0 for r in rows) and all(s["exit"] == 0 for s in smoke) else 1


if __name__ == "__main__":
    raise SystemExit(main())
