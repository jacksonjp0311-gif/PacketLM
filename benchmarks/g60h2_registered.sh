#!/bin/sh
# G60H2 registered run (docs/G60H2.md §11). Records lock times, load and other heavy processes.
set -e
cd "$(dirname "$0")/.."
OUT=artifacts/g60h2_reg
mkdir -p $OUT
LOCK=/workspace/REGISTERED_RUN.lock
[ -e $LOCK ] && { echo "lock exists: $(cat $LOCK)"; exit 1; }
echo "g60h2 $(date +%Y-%m-%dT%H:%M:%S%z) $(git rev-parse --short HEAD)" > $LOCK
echo "lock_created $(date +%Y-%m-%dT%H:%M:%S%z)" > $OUT/lock_times.txt
( while [ -e $LOCK ]; do echo "== $(date +%H:%M:%S) load $(cut -d' ' -f1-3 /proc/loadavg)"; ps -eo pid,pcpu,etime,args --sort=-pcpu | awk 'NR>1 && $2>20' | cut -c1-160; sleep 30; done ) > $OUT/load_log.txt 2>&1 &
G60H_SCALE_WORKERS=1 python3 benchmarks/g60h_scale.py --config e --seeds 551,552,553,554,555,556,557 --out g60h2_reg_scale > $OUT/scale.out 2>&1
G60H_WORKERS=4 python3 benchmarks/g60h2.py --config e --margin 1 --out g60h2_reg_e1 > $OUT/gate_e1.out 2>&1
G60H_WORKERS=4 python3 benchmarks/g60h2.py --config e --margin 2 --out g60h2_reg_e2 > $OUT/gate_e2.out 2>&1
G60H_WORKERS=4 python3 benchmarks/g60h2.py --config p --margin 1 --out g60h2_reg_p1 > $OUT/gate_p1.out 2>&1
G60H_WORKERS=4 python3 benchmarks/g60h2.py --config e --margin 1 --only decoy --out g60h2_reg_decoy_e > $OUT/decoy_e.out 2>&1
G60H_WORKERS=4 python3 benchmarks/g60h2.py --config o --margin 1 --only decoy --out g60h2_reg_decoy_o > $OUT/decoy_o.out 2>&1
echo "timed_done $(date +%Y-%m-%dT%H:%M:%S%z)" >> $OUT/lock_times.txt
rm -f $LOCK
echo "lock_deleted $(date +%Y-%m-%dT%H:%M:%S%z)" >> $OUT/lock_times.txt
G60H_WORKERS=4 python3 benchmarks/g60h2.py --config d --margin 1 --out g60h2_reg_d1 > $OUT/guard_d1.out 2>&1
python3 benchmarks/g60h2_ablation.py artifacts/g60h2_reg_e1 artifacts/g60h2_reg_p1 $OUT/ablation.json > /dev/null 2>&1
python3 -m packetlm.hdc.test_hdc > $OUT/test_hdc.txt 2>&1 || true
python3 benchmarks/g60h2_mutations.py --out $OUT/mutations.json > $OUT/mutations.out 2>&1
echo "all_done $(date +%Y-%m-%dT%H:%M:%S%z)" >> $OUT/lock_times.txt
