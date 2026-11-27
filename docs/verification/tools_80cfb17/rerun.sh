#!/bin/sh
# Verifier partial reruns (guarded): part S k alone with 1 worker (seeds 291,292; 16k, 64k); then gate comp 301 + unrel 321 (3 workers); then work_probe.
cd "$(dirname "$0")/../../.."; G=docs/verification/tools_80cfb17/guard.sh; L=docs/verification/tools_80cfb17/logs
echo "start $(date +%T) load $(cut -d' ' -f1-3 /proc/loadavg)"
G59_WORKERS=1 G59_REF_ROOT=/tmp/w33565b0 $G python3 benchmarks/g59_scale.py --seeds 291,292 --sizes 16000,64000 --arms k --out vrerun_scale_k1 > $L/rerun_scale_k1.json 2>&1; echo "scale rc=$? $(date +%T) load $(cut -d' ' -f1-3 /proc/loadavg)"
G59_WORKERS=3 $G python3 benchmarks/g59.py --only comp,unrel --seeds-comp 301 --seeds-unrel 321 --out vrerun_gate > $L/rerun_gate.json 2>&1; echo "gate rc=$? $(date +%T) load $(cut -d' ' -f1-3 /proc/loadavg)"
for n in 16000 64000; do $G python3 docs/verification/tools_80cfb17/work_probe.py 292 $n > $L/work_probe2_292_$n.log 2>&1; done; echo "probe done $(date +%T)"
