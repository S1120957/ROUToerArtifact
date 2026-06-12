#!/usr/bin/env bash
# Register each source channel's endorsement policy + verification keys on the
# coordination channel (RegisterSourcePolicy). Replace the HMAC keyHex values
# with your real source-MSP verification material for a multi-MSP deployment.
set -euo pipefail
: "${FABRIC_SAMPLES:?set FABRIC_SAMPLES}"
cd "$FABRIC_SAMPLES/test-network"
. ./scripts/envVar.sh 2>/dev/null || true
echo "[register-policies] invoke anchor.RegisterSourcePolicy for each source channel."
echo "  Example (peer CLI), 2-of-3 policy for domain-a-channel:"
cat <<'JSON'
  POLICY='{"members":[{"id":"peer0","keyHex":"6b30"},{"id":"peer1","keyHex":"6b31"},{"id":"peer2","keyHex":"6b32"}],"quorum":2}'
  peer chaincode invoke -C coordination-channel -n anchor \
    -c "{\"function\":\"RegisterSourcePolicy\",\"Args\":[\"domain-a-channel\",\"$POLICY\"]}"
JSON
