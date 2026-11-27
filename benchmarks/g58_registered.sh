#!/bin/sh
# G58 registered run (docs/G58.md): lock created immediately before, deleted right after; the lock's
# create/delete times are written to artifacts/g58_lock.json.
set -e
cd "$(dirname "$0")/.."
LOCK=/workspace/REGISTERED_RUN.lock
[ -e "$LOCK" ] && { echo "lock exists"; exit 1; }
mkdir -p artifacts
C=$(date +%Y-%m-%dT%H:%M:%S%z)
echo "$C G58 registered run (library scaling 261-267; L1/L2/L3 comp 271-277, unrel 281-287) head $(git rev-parse HEAD)" > "$LOCK"
set +e
python3 benchmarks/g58_libscale.py --out g58_libscale > artifacts/g58_libscale_stdout.json 2>&1; S=$?
python3 benchmarks/g58.py --out g58 > artifacts/g58_stdout.json 2>&1; L=$?
rm -f "$LOCK"
D=$(date +%Y-%m-%dT%H:%M:%S%z)
printf '{"lock_created": "%s", "lock_deleted": "%s", "libscale_rc": %s, "l1l3_rc": %s}\n' "$C" "$D" "$S" "$L" > artifacts/g58_lock.json
cat artifacts/g58_lock.json
