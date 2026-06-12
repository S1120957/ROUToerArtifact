#!/usr/bin/env bash
# Start the Fabric test-network (single host). Requires FABRIC_SAMPLES set.
set -euo pipefail
: "${FABRIC_SAMPLES:?set FABRIC_SAMPLES to your fabric-samples checkout}"
cd "$FABRIC_SAMPLES/test-network"
./network.sh down || true
./network.sh up -ca -s couchdb
echo "[network-up] test-network is up (CA + CouchDB)."
