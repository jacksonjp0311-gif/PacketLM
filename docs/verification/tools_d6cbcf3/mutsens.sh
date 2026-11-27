#!/bin/sh
# usage: mutsens.sh NAME ; applies serve mutation NAME (from packetlm/mutations.py, or verifier extras) in a copy and runs the verifier's serve tools
N=$1; D=/tmp/plmut_$N; rm -rf $D; mkdir -p $D
cd /workspace/pl-verify && tar --exclude=./artifacts --exclude=./.git -cf - . | tar -xf - -C $D
cd $D && python3 - "$N" <<'P'
import sys, re
n = sys.argv[1]
extra = {"v_no_finish": ('        eng.finish()\n        validate_lean(', '        validate_lean(', "serve.py"),
         "v_stale_journal_dropped": ('            elif head["base"] is not None and head["base"] == bak', '            elif head["base"] == bak', "serve.py")}
src = open("packetlm/mutations.py").read()
import ast
if n in extra:
    a, b, f = extra[n]
else:
    m = re.search(r'"%s": \((.*?)\),\n' % n, src, re.S)
    a, b, f = ast.literal_eval("(" + m.group(1) + ")")
p = "packetlm/" + f
s = open(p).read(); assert s.count(a) == 1, ("anchor", n); open(p, "w").write(s.replace(a, b))
print("applied", n)
P
T=docs/verification/tools_d6cbcf3
echo "== diff"; timeout 1200 python3 $T/serve_diff.py 15 91 --crash 2>&1 | head -3 | cut -c1-400
echo "== inproc"; timeout 1200 python3 $T/serve_diff.py 8 92 --inproc 2>&1 | head -3 | cut -c1-400
echo "== faults"; timeout 1200 python3 $T/serve_faults.py 3 93 2>&1 | head -2 | cut -c1-400
rm -rf $D
