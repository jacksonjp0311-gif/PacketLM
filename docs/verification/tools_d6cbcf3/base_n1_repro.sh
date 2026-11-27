#!/bin/sh
# Verifier repro (3e2783c): base mode (no --programs). After 'fact a ra x' the qualified version rel:ra
# is undetermined on its own example a -> b, re-acquisition records no candidate, and the version
# stays qualified (the N1 fix covers only the programs path). Run from the repo root.
f=/tmp/base_n1.json; rm -f $f $f.bak
python3 -m packetlm.engine $f --answers 'fact a ra b' 'fact c ra d' 'fact e ra f' 'example kk: a -> b' 'example kk: c -> d' 'fact a ra x' 'show kk' 'what is e kk'
python3 -c "
import json; s=json.load(open('$f'))['state']; v=s['capabilities']['kk']['versions'][-1]
print('candidate', s['hypotheses']['kk'].get('candidate'), '| status', v['status'], '| history', v['history'])"
