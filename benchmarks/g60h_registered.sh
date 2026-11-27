#!/bin/sh
# G60H registered run (docs/G60H.md §11). Records lock times, load and other heavy processes.
set -e
cd "$(dirname "$0")/.."
OUT=artifacts/g60h_reg
mkdir -p $OUT
LOCK=/workspace/REGISTERED_RUN.lock
[ -e $LOCK ] && { echo "lock exists: $(cat $LOCK)"; exit 1; }
echo "g60h $(date +%Y-%m-%dT%H:%M:%S%z) $(git rev-parse --short HEAD)" > $LOCK
echo "lock_created $(date +%Y-%m-%dT%H:%M:%S%z)" > $OUT/lock_times.txt
( while [ -e $LOCK ]; do echo "== $(date +%H:%M:%S) load $(cut -d' ' -f1-3 /proc/loadavg)"; ps -eo pid,pcpu,etime,args --sort=-pcpu | awk 'NR>1 && $2>20' | cut -c1-160; sleep 30; done ) > $OUT/load_log.txt 2>&1 &
G60H_SCALE_WORKERS=1 python3 benchmarks/g60h_scale.py --out g60h_reg_scale > $OUT/scale.out 2>&1
G60H_WORKERS=4 python3 benchmarks/g60h.py --out g60h_reg_m1 --margin 1 > $OUT/gate_m1.out 2>&1
G60H_WORKERS=4 python3 benchmarks/g60h.py --out g60h_reg_m2 --margin 2 > $OUT/gate_m2.out 2>&1
echo "timed_done $(date +%Y-%m-%dT%H:%M:%S%z)" >> $OUT/lock_times.txt
python3 benchmarks/g60h_capacity.py --out g60h_reg_capacity > $OUT/capacity.out 2>&1
rm -f $LOCK
echo "lock_deleted $(date +%Y-%m-%dT%H:%M:%S%z)" >> $OUT/lock_times.txt
