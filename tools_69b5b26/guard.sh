#!/bin/sh
# wait while a registered run holds the lock, then exec
while [ -e /workspace/REGISTERED_RUN.lock ]; do sleep 10; done
exec "$@"
