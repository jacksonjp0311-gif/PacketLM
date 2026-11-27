"""Profiling shim (diagnostic only, docs/G53.md): runs `packetlm.engine` main under cProfile and
appends a per-call summary line (JSON) to $PL_PROF_OUT. Stdout is the engine's own JSON."""
import cProfile
import json
import os
import pstats
import resource
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FUNCS = ["open", "save", "_idx", "tell", "acquire", "hypotheses", "_scan", "primitives", "expand", "execute",
         "_predictions", "investigate", "answer", "ask", "review", "_requalify", "_fc_requalify", "correct",
         "_drop", "_retire", "_adopt", "_component", "evaluate"]

t_start = sum(resource.getrusage(resource.RUSAGE_SELF)[:2])
pr = cProfile.Profile()
pr.enable()
import packetlm.engine as E  # noqa: E402
rc = E.main(sys.argv[1:])
pr.disable()
if os.environ.get("PL_PROF_DUMP"):  # full profile of every call, for drill-down
    pr.dump_stats(os.path.join(os.environ["PL_PROF_DUMP"], f"{os.getpid()}_{time.time_ns()}.prof"))
st = pstats.Stats(pr)
cum = {}
for (fn, line, name), (cc, nc, tt, ct, callers) in st.stats.items():
    if fn.endswith("packetlm/engine.py") and name in FUNCS:
        c = cum.setdefault(name, [0.0, 0])
        c[0] += ct
        c[1] += nc
    if name == "<module>" and fn.endswith("packetlm/engine.py"):
        cum.setdefault("import_engine", [0.0, 0])[0] += ct
    if name in ("loads", "dumps", "load", "dump") and "json" in fn:
        c = cum.setdefault("json_" + name, [0.0, 0])
        c[0] += ct
        c[1] += nc
args = [a for a in sys.argv[1:] if not a.startswith("--")]
lines = args[1:]
kind = ("maint" if any(l.startswith(("correct ", "requalify", "transfer", "retire")) for l in lines) else
        "eval" if lines and all(l.startswith("what is") for l in lines) else "teach")
rec = {"state": args[0], "kind": kind, "n_lines": len(lines), "flags": [a for a in sys.argv[1:] if a.startswith("--")],
       "state_bytes": os.path.getsize(args[0]) if os.path.exists(args[0]) else 0,
       "cpu_total_s": round(sum(resource.getrusage(resource.RUSAGE_SELF)[:2]), 4), "cpu_pre_profile_s": round(t_start, 4),
       "prof_total_s": round(sum(v[3] for k, v in st.stats.items() if not v[4]), 4),
       "funcs": {k: [round(v[0], 5), v[1]] for k, v in cum.items()}}
with open(os.environ["PL_PROF_OUT"], "a") as f:
    f.write(json.dumps(rec) + "\n")
raise SystemExit(rc)
