#!/bin/sh
# G57b registered run (docs/G57b.md): lock created immediately before, deleted right after; the
# lock's create/delete times are written to artifacts/g57b_lock.json (Low 2 of verify-35bda6b).
set -e
cd "$(dirname "$0")/.."
LOCK=/workspace/REGISTERED_RUN.lock
[ -e "$LOCK" ] && { echo "lock exists"; exit 1; }
mkdir -p artifacts
C=$(date +%Y-%m-%dT%H:%M:%S%z)
echo "$C G57b registered run (part S 231-237; L1/L3 comp 241-247, unrel 251-257) head $(git rev-parse HEAD)" > "$LOCK"
set +e
python3 benchmarks/g57b_scale.py --out g57b_scale > artifacts/g57b_scale_stdout.json 2>&1; S=$?
python3 benchmarks/g57b.py --out g57b > artifacts/g57b_stdout.json 2>&1; L=$?
rm -f "$LOCK"
D=$(date +%Y-%m-%dT%H:%M:%S%z)
printf '{"lock_created": "%s", "lock_deleted": "%s", "scale_rc": %s, "l1l3_rc": %s}\n' "$C" "$D" "$S" "$L" > artifacts/g57b_lock.json
cat artifacts/g57b_lock.json
