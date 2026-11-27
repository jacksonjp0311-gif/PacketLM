#!/bin/sh
# G59 registered run (docs/G59.md): lock created immediately before, deleted right after; the lock's
# create/delete times and each part's return code are written to artifacts/g59_lock.json.
set -e
cd "$(dirname "$0")/.."
LOCK=/workspace/REGISTERED_RUN.lock
[ -e "$LOCK" ] && { echo "lock exists"; exit 1; }
mkdir -p artifacts
C=$(date +%Y-%m-%dT%H:%M:%S%z)
echo "$C G59 registered run (part S 291-297; comp 301-307, comp-rep 311-317, unrel 321-327, mixed 331-337, long 341-347) head $(git rev-parse HEAD)" > "$LOCK"
set +e
python3 benchmarks/g59_scale.py --out g59_scale > artifacts/g59_scale_stdout.json 2>&1; S=$?
python3 benchmarks/g59.py --out g59 > artifacts/g59_stdout.json 2>&1; G=$?
rm -f "$LOCK"
D=$(date +%Y-%m-%dT%H:%M:%S%z)
printf '{"lock_created": "%s", "lock_deleted": "%s", "scale_rc": %s, "gate_rc": %s}\n' "$C" "$D" "$S" "$G" > artifacts/g59_lock.json
cat artifacts/g59_lock.json
