#!/bin/sh
# Verifier: apply one textual mutation (python3 -c replace, exactly once) to a /tmp copy of the tree and run
# (a) routed_diff with the G58 audit and churn, (b) the builder's g58_diff + contract_fuzz, (c) g44 (timeout).
# Usage: mutant_check.sh NAME OLD NEW  (OLD/NEW as Python string literals)
set -u
N=$1; OLD=$2; NEW=$3
ROOT=$(cd "$(dirname "$0")/../../.." && pwd); D=/tmp/mutchk_$N; rm -rf $D; mkdir -p $D
cp -r $ROOT/packetlm $ROOT/benchmarks $D/; mkdir -p $D/docs/verification; cp -r $ROOT/docs/verification/tools_33565b0 $D/docs/verification/
python3 - "$D/packetlm/engine.py" "$OLD" "$NEW" <<'PY'
import sys, ast
p, old, new = sys.argv[1], ast.literal_eval(sys.argv[2]), ast.literal_eval(sys.argv[3])
s = open(p).read(); assert s.count(old) == 1, s.count(old); open(p, "w").write(s.replace(old, new)); print("applied")
PY
cd $D
echo "== g44 (timeout 400 s)"; timeout 400 python3 -m packetlm.g44_test > g44.out 2>&1; echo "g44 rc=$?"; python3 -c "import json;d=json.load(open('artifacts/g44_receipt.json'));print('failed',d['failed'])" 2>/dev/null
echo "== g58_diff 60 sessions seed 7001 + contract_fuzz 60 seed 7002"
timeout 900 python3 -c "
import json; from packetlm import g58_diff as g
r=g.run(60,7001); print(json.dumps({k:r[k] for k in ('ok','sessions','calls','audit_violations','mismatch')})[:600])
f=g.contract_fuzz(60,7002,2); print(json.dumps({k:f[k] for k in ('ok','sessions','reviews','transitions','audit_violations','audit_first')})[:600])"; echo "rc=$?"
echo "== routed_diff 60 sessions audit churn lib mix K3"
timeout 1500 python3 docs/verification/tools_33565b0/routed_diff.py 60 7003 --churn --lib mix --audit --K 3 --snap 8 --arms REF,XR | head -4; echo "rc=$?"
