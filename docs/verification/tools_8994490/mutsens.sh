#!/bin/sh
# Verifier: sensitivity of incr_diff.py — apply each builder G57b mutation (packetlm/mutations.py)
# to a /tmp copy and run the differential (60 sessions, K=3, snap 8, --deep) against it.
cd "$(dirname "$0")/../../.."
OUT=docs/verification/tools_8994490/logs/mutsens; mkdir -p $OUT
for m in $(python3 -c "from packetlm.mutations import MUTATIONS as M; print(' '.join(k for k in M if k.startswith(('g57b_','v35_'))))"); do
  d=/tmp/mutsens_$m; rm -rf $d; mkdir -p $d; cp -r packetlm data benchmarks $d/
  python3 - "$m" "$d" <<'PY'
import sys; sys.path.insert(0, '.')
from packetlm.mutations import MUTATIONS
old, new, *t = MUTATIONS[sys.argv[1]]
p = f"{sys.argv[2]}/packetlm/{t[0] if t else 'engine.py'}"
s = open(p).read(); assert s.count(old) == 1, "site"; open(p, "w").write(s.replace(old, new))
PY
  PL_ROOT=$d timeout 900 python3 docs/verification/tools_8994490/incr_diff.py 60 77 --K 3 --snap 8 --deep > $OUT/$m.log 2>&1
  echo "$m $(head -1 $OUT/$m.log | python3 -c 'import json,sys
try:
  d=json.loads(sys.stdin.read()); print({k:d.get(k,0) for k in ("calls","reply_diffs","state_diffs","stats_diffs","deep_diffs","errors","final_bytes_diffs","journal_diffs")})
except Exception as e: print("unparsable", e)')"
  rm -rf $d
done
