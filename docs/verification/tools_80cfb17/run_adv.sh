#!/bin/sh
# verifier adversarial runs (guarded); each writes logs/adv/<name>.log
cd "$(dirname "$0")"; G=./guard.sh; L=logs/adv
run() { n=$1; shift; $G python3 part_diff.py "$@" > $L/$n.log 2>&1; echo "$n rc=$? $(date +%T)"; }
case "$1" in
a) run p1_real_audit_K3 40 5901 --deep --audit --churn --lib mix --K 3 --snap 8
   run p4_append 12 5904 --appendonly 300 --K 64 --snap 1000 --lib 16 --deep ;;
b) run p2_dense_audit 40 5902 --deep --audit --churn --lib mix --K 3 --snap 8 --codes dense
   run p5_pad 20 5905 --pad mix --churn --lib mix --deep ;;
c) run p3_block_audit 30 5903 --deep --audit --churn --lib mix --K 64 --snap 64 --codes block
   run x1_k 60 5911 --churn --lib mix --arms XK64 --dump $L/x1_k.json
   PL_ROOT=/tmp/w33565b0 run x1_r0 60 5911 --churn --lib mix --arms XR64 --dump $L/x1_r0.json ;;
esac
