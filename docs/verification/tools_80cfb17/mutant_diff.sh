#!/bin/sh
# Verifier: apply one packetlm/mutations.py mutation in a /tmp copy, run part_diff (audit on unless NOAUDIT=1) there.
# Usage: mutant_diff.sh NAME N SEED [part_diff args...]
cd "$(dirname "$0")/../../.."; NAME=$1; N=$2; S=$3; shift 3
D=/tmp/mut80_$NAME; rm -rf $D; mkdir -p $D; cp -r packetlm benchmarks $D/
python3 - "$NAME" "$D" <<'PY'
import sys; sys.path.insert(0, '.')
from packetlm.mutations import MUTATIONS
name, d = sys.argv[1], sys.argv[2]; m = MUTATIONS[name]
old, new = m[0], m[1]; tgt = m[2] if len(m) > 2 else 'engine.py'
p = f"{d}/packetlm/{tgt}"; s = open(p).read(); assert s.count(old) == 1, "site"; open(p, 'w').write(s.replace(old, new)); print("applied", name, tgt)
PY
A=--audit; [ "$NOAUDIT" = 1 ] && A=
PL_ROOT=$D ./docs/verification/tools_80cfb17/guard.sh python3 docs/verification/tools_80cfb17/part_diff.py $N $S $A "$@" --arms REF,XK64 2>&1 | head -c 1500; echo
