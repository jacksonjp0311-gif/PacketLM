#!/bin/sh
# run "$@" only when no registered timing run holds the lock; waits (30 s polls) otherwise
while [ -e /workspace/REGISTERED_RUN.lock ]; do echo "lock present $(date +%T), waiting" >&2; sleep 30; done
exec "$@"
