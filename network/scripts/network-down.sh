#!/usr/bin/env bash
set -euo pipefail
: "${FABRIC_SAMPLES:?set FABRIC_SAMPLES}"
cd "$FABRIC_SAMPLES/test-network"
./network.sh down
echo "[network-down] done."
