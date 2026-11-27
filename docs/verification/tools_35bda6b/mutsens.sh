#!/bin/sh
# usage: mutsens.sh NAME ; applies mutation NAME from packetlm/mutations.py in a copy and runs the verifier's indexed_diff
N=$1; D=/tmp/plmut9_$N; rm -rf $D; mkdir -p $D
cd /workspace/pl-verify && tar --exclude=./artifacts --exclude=./.git -cf - . | tar -xf - -C $D
cd $D && python3 - "$N" <<'P'
import sys, re, ast
n = sys.argv[1]
src = open("packetlm/mutations.py").read()
m = re.search(r"""["']%s["']: \((.*?)\),(  #[^\n]*)?\n""" % n, src, re.S)
a, b, *f = ast.literal_eval("(" + m.group(1) + ")")
p = "packetlm/" + (f[0] if f else "engine.py")
s = open(p).read(); assert s.count(a) == 1, ("anchor", n, s.count(a)); open(p, "w").write(s.replace(a, b))
print("applied", n, "to", p)
P
timeout 1500 python3 docs/verification/tools_35bda6b/indexed_diff.py 80 201 2>&1 | head -3 | cut -c1-600
rm -rf $D
