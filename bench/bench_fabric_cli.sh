#!/usr/bin/env bash
#
# bench_fabric_cli.sh -- measure REAL Fabric latency for the three Table 2 rows
# using the peer CLI against the running test-network. It reuses the identities
# network.sh already generated, so there is NO gateway/identity wiring to do.
#
# Prereqs (see network/README.md): FABRIC_SAMPLES set, `make fabric-up` and
# `make fabric-deploy` already run, Docker running, and `jq` + node + python3
# installed. Run from the repo root:  bash bench/bench_fabric_cli.sh
#
# Output: bench/bench_results.json  (consumed by `make tables`).
#
# It measures:
#   - CommitWindow over N events  (source chaincode; O(N) build)  -> submit
#   - Anchor validation           (coordination chaincode)        -> submit
#   - GetAnchors                  (coordination chaincode)         -> query
# Median and p95 over ITERS iterations after WARMUP discarded.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

# ---- preconditions --------------------------------------------------------
: "${FABRIC_SAMPLES:?set FABRIC_SAMPLES to your fabric-samples checkout}"
for tool in jq node python3; do
  command -v "$tool" >/dev/null || { echo "ERROR: '$tool' not found on PATH"; exit 1; }
done
export PATH="$FABRIC_SAMPLES/bin:$PATH"
export FABRIC_CFG_PATH="$FABRIC_SAMPLES/config"
command -v peer >/dev/null || { echo "ERROR: 'peer' not found ($FABRIC_SAMPLES/bin missing?)"; exit 1; }
docker ps --format '{{.Names}}' 2>/dev/null | grep -q 'peer0.org1' \
  || { echo "ERROR: test-network not running. Run 'make fabric-up && make fabric-deploy' first."; exit 1; }

# ---- parameters (override via env) ----------------------------------------
SRC_CH="${SRC_CH:-domain-a-channel}"
COORD_CH="${COORD_CH:-coordination-channel}"
CC_SRC="${CC_SRC:-commitWindow}"
CC_COORD="${CC_COORD:-anchor}"
NEVENTS="${NEVENTS:-100}"        # keep 100 to match the "CommitWindow N=100" table row
ITERS="${ITERS:-20}"
WARMUP="${WARMUP:-5}"
STEP="${STEP:-100}"              # height span per anchored window
QUORUM=2
KEY0=6b30 KEY1=6b31 KEY2=6b32    # hex of "k0","k1","k2"; must match RegisterSourcePolicy
SALT_B64="$(printf 'bench-salt-key' | base64 -w0)"

# ---- test-network identity (Org1 admin) + TLS material --------------------
TN="$FABRIC_SAMPLES/test-network"
# TLS material: paths differ slightly between CA and cryptogen modes, so fall
# back to the alternate location if the primary is absent, then verify.
ORDERER_CA="$TN/organizations/ordererOrganizations/example.com/tlsca/tlsca.example.com-cert.pem"
[ -f "$ORDERER_CA" ] || ORDERER_CA="$TN/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem"
ORG1_CA="$TN/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt"
[ -f "$ORG1_CA" ] || ORG1_CA="$TN/organizations/peerOrganizations/org1.example.com/tlsca/tlsca.org1.example.com-cert.pem"
ORG2_CA="$TN/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt"
[ -f "$ORG2_CA" ] || ORG2_CA="$TN/organizations/peerOrganizations/org2.example.com/tlsca/tlsca.org2.example.com-cert.pem"
for f in "$ORDERER_CA" "$ORG1_CA" "$ORG2_CA"; do
  [ -f "$f" ] || { echo "ERROR: TLS cert not found: $f (is the network up and deployed?)"; exit 1; }
done
export CORE_PEER_TLS_ENABLED=true
export CORE_PEER_LOCALMSPID=Org1MSP
export CORE_PEER_TLS_ROOTCERT_FILE="$ORG1_CA"
export CORE_PEER_MSPCONFIGPATH="$TN/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp"
export CORE_PEER_ADDRESS=localhost:7051

# invoke that targets both orgs (commitWindow uses the default majority policy)
INVOKE=(peer chaincode invoke -o localhost:7050
        --ordererTLSHostnameOverride orderer.example.com --tls --cafile "$ORDERER_CA"
        --peerAddresses localhost:7051 --tlsRootCertFiles "$ORG1_CA"
        --peerAddresses localhost:9051 --tlsRootCertFiles "$ORG2_CA")

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
ms_now() { date +%s%N; }            # nanoseconds
elapsed_ms() { echo $(( ($(ms_now) - $1) / 1000000 )); }

echo "== bench: SRC_CH=$SRC_CH COORD_CH=$COORD_CH NEVENTS=$NEVENTS ITERS=$ITERS WARMUP=$WARMUP =="

# ---- 0) register the source policy on the coordination channel ------------
POLICY="$(jq -nc --arg k0 "$KEY0" --arg k1 "$KEY1" --arg k2 "$KEY2" \
  '{members:[{id:"peer0",keyHex:$k0},{id:"peer1",keyHex:$k1},{id:"peer2",keyHex:$k2}],quorum:2}')"
CARG="$(jq -nc --arg s "$SRC_CH" --arg p "$POLICY" '{function:"Anchor:RegisterSourcePolicy",Args:[$s,$p]}')"
echo "-- registering source policy"
"${INVOKE[@]}" -C "$COORD_CH" -n "$CC_COORD" -c "$CARG" --waitForEvent >/dev/null 2>&1 || true

# ---- 1) populate N events on the source channel (setup; not timed) --------
echo "-- populating $NEVENTS events (setup, not timed; this is the slow part)"
TR="$(jq -nc --arg p "$(printf 'x' | base64 -w0)" '{payload:$p}')"
for i in $(seq 0 $((NEVENTS-1))); do
  CARG="$(jq -nc --arg eid "tx-$i" --arg h "$i" --arg ti "0" --arg sd "$SRC_CH" \
    '{function:"CommitWindow:RecordEvent",Args:[$eid,$h,$ti,$sd]}')"
  "${INVOKE[@]}" -C "$SRC_CH" -n "$CC_SRC" -c "$CARG" --transient "$TR" --waitForEvent >/dev/null 2>&1
  (( (i+1) % 20 == 0 )) && echo "   .. $((i+1))/$NEVENTS"
done

# ---- 2) time CommitWindow over [0, N-1] -----------------------------------
echo "-- timing CommitWindow (N=$NEVENTS)"
TR="$(jq -nc --arg k "$SALT_B64" '{saltKey:$k}')"
CARG="$(jq -nc --arg s "$SRC_CH" --arg w "1" --arg a "0" --arg b "$((NEVENTS-1))" \
  '{function:"CommitWindow:CommitWindow",Args:[$s,$w,$a,$b]}')"
: > "$TMP/commit.txt"
for _ in $(seq 1 $((WARMUP+ITERS))); do
  t0="$(ms_now)"
  "${INVOKE[@]}" -C "$SRC_CH" -n "$CC_SRC" -c "$CARG" --transient "$TR" --waitForEvent >/dev/null 2>&1
  elapsed_ms "$t0" >> "$TMP/commit.txt"
done

# ---- 3) time Anchor (monotonic windows; resume past any existing anchors) --
echo "-- timing Anchor"
CARG_GET="$(jq -nc --arg s "$SRC_CH" '{function:"Anchor:GetAnchors",Args:[$s]}')"
EXISTING="$(peer chaincode query -C "$COORD_CH" -n "$CC_COORD" -c "$CARG_GET" 2>/dev/null || echo '[]')"
START_W=$(( $(echo "$EXISTING" | jq 'length' 2>/dev/null || echo 0) + 1 ))
: > "$TMP/anchor.txt"
w=$START_W
for _ in $(seq 1 $((WARMUP+ITERS))); do
  a=$(( (w-1)*STEP )); b=$(( w*STEP - 1 ))
  PAYLOAD="$(node "$HERE/make_anchor_payload.js" "$SRC_CH" "$w" "$a" "$b" "$STEP" "$QUORUM" "$KEY0" "$KEY1")"
  CMT="$(echo "$PAYLOAD" | sed -n 1p)"; ENDO="$(echo "$PAYLOAD" | sed -n 2p)"
  CARG="$(jq -nc --arg c "$CMT" --arg e "$ENDO" '{function:"Anchor:Anchor",Args:[$c,$e]}')"
  t0="$(ms_now)"
  "${INVOKE[@]}" -C "$COORD_CH" -n "$CC_COORD" -c "$CARG" --waitForEvent >/dev/null 2>&1
  elapsed_ms "$t0" >> "$TMP/anchor.txt"
  w=$((w+1))
done

# ---- 4) time GetAnchors (query) -------------------------------------------
echo "-- timing GetAnchors (query)"
: > "$TMP/get.txt"
for _ in $(seq 1 $((WARMUP+ITERS))); do
  t0="$(ms_now)"
  peer chaincode query -C "$COORD_CH" -n "$CC_COORD" -c "$CARG_GET" >/dev/null 2>&1
  elapsed_ms "$t0" >> "$TMP/get.txt"
done

# ---- 5) aggregate into bench_results.json ---------------------------------
python3 "$HERE/_aggregate.py" "$HERE/bench_results.json" "$WARMUP" \
  "CommitWindow N=$NEVENTS" "$TMP/commit.txt" \
  "Anchor validate"        "$TMP/anchor.txt" \
  "GetAnchors + verify"    "$TMP/get.txt"

echo "DONE. Now run:  python3 experiments/gen_tables.py   (or: make tables)"
