#!/usr/bin/env bash
# Create the three source channels and the coordination channel.
set -euo pipefail
: "${FABRIC_SAMPLES:?set FABRIC_SAMPLES}"
cd "$FABRIC_SAMPLES/test-network"
for ch in domain-a-channel domain-b-channel domain-c-channel coordination-channel; do
  ./network.sh createChannel -c "$ch"
  echo "[create-channels] created $ch"
done
