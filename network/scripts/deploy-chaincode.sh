#!/usr/bin/env bash
# Deploy commitWindow to each source channel and anchor to the coordination
# channel. CC_SRC_PATH points at this repo's chaincode/ directory.
set -euo pipefail
: "${FABRIC_SAMPLES:?set FABRIC_SAMPLES}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$FABRIC_SAMPLES/test-network"

for ch in domain-a-channel domain-b-channel domain-c-channel; do
  ./network.sh deployCC -c "$ch" -ccn commitWindow \
    -ccp "$REPO/chaincode" -ccl javascript \
    -cci "org.hyperledger.fabric:GetMetadata"
  echo "[deploy] commitWindow -> $ch"
done

# coordination channel: MAJORITY endorsement
./network.sh deployCC -c coordination-channel -ccn anchor \
  -ccp "$REPO/chaincode" -ccl javascript \
  -ccep "OR('Org1MSP.peer','Org2MSP.peer')"
echo "[deploy] anchor -> coordination-channel"
