#!/bin/sh
# Verifier: g44, suite, G45, mutations on a clean copy of 80cfb17 (guarded by the lock)
cd "$(dirname "$0")/../../.."
L=docs/verification/tools_80cfb17/logs
G=docs/verification/tools_80cfb17/guard.sh
echo "start $(date +%T) head $(git rev-parse --short HEAD) porcelain=[$(git status --porcelain -- packetlm benchmarks)]"
$G python3 -m packetlm.g44_test > $L/g44.log 2>&1; echo "g44 rc=$? $(date +%T)"
$G python3 -m packetlm.suite > $L/suite.log 2>&1; echo "suite rc=$? $(date +%T)"
$G python3 -m packetlm.g45_test > $L/g45.log 2>&1; echo "g45 rc=$? $(date +%T)"
PACKETLM_MUT_WORKERS=4 $G python3 -m packetlm.mutations > $L/mutations.log 2>&1; echo "mut rc=$? $(date +%T)"
