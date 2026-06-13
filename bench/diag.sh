#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
: "${FABRIC_SAMPLES:?set FABRIC_SAMPLES}"
export PATH="$FABRIC_SAMPLES/bin:$PATH"
export FABRIC_CFG_PATH="$FABRIC_SAMPLES/config"

SRC_CH=domain-a-channel; COORD_CH=coordination-channel
CC_SRC=commitWindow; CC_COORD=anchor
KEY0=6b30 KEY1=6b31 KEY2=6b32; QUORUM=2
SALT_B64="$(printf 'bench-salt-key' | base64 -w0)"

TN="$FABRIC_SAMPLES/test-network"
ORDERER_CA="$TN/organizations/ordererOrganizations/example.com/tlsca/tlsca.example.com-cert.pem"
ORG1_CA="$TN/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt"
ORG2_CA="$TN/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt"
export CORE_PEER_TLS_ENABLED=true CORE_PEER_LOCALMSPID=Org1MSP
export CORE_PEER_TLS_ROOTCERT_FILE="$ORG1_CA"
export CORE_PEER_MSPCONFIGPATH="$TN/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp"
export CORE_PEER_ADDRESS=localhost:7051
INVOKE=(peer chaincode invoke -o localhost:7050 --ordererTLSHostnameOverride orderer.example.com
        --tls --cafile "$ORDERER_CA"
        --peerAddresses localhost:7051 --tlsRootCertFiles "$ORG1_CA"
        --peerAddresses localhost:9051 --tlsRootCertFiles "$ORG2_CA")

step(){ echo; echo "########## $* ##########"; }

step "1) RegisterSourcePolicy"
POLICY="$(jq -nc --arg k0 "$KEY0" --arg k1 "$KEY1" --arg k2 "$KEY2" '{members:[{id:"peer0",keyHex:$k0},{id:"peer1",keyHex:$k1},{id:"peer2",keyHex:$k2}],quorum:2}')"
"${INVOKE[@]}" -C "$COORD_CH" -n "$CC_COORD" \
  -c "$(jq -nc --arg s "$SRC_CH" --arg p "$POLICY" '{function:"Anchor:RegisterSourcePolicy",Args:[$s,$p]}')" --waitForEvent
echo "RegisterSourcePolicy exit=$?"

step "2) RecordEvent x3 (heights 0,1,2)"
for i in 0 1 2; do
  "${INVOKE[@]}" -C "$SRC_CH" -n "$CC_SRC" \
    -c "$(jq -nc --arg eid "tx-$i" --arg h "$i" --arg sd "$SRC_CH" '{function:"CommitWindow:RecordEvent",Args:[$eid,$h,"0",$sd]}')" \
    --transient "$(jq -nc --arg p "$(printf x | base64 -w0)" '{payload:$p}')" --waitForEvent
  echo "  RecordEvent $i exit=$?"
done

step "3) CommitWindow over [0,2]  <-- the failing call; FULL output follows"
"${INVOKE[@]}" -C "$SRC_CH" -n "$CC_SRC" \
  -c "$(jq -nc --arg s "$SRC_CH" '{function:"CommitWindow:CommitWindow",Args:[$s,"1","0","2"]}')" \
  --transient "$(jq -nc --arg k "$SALT_B64" '{saltKey:$k}')" --waitForEvent
echo "CommitWindow exit=$?"

step "4) GetCommitment(1) [query]"
peer chaincode query -C "$SRC_CH" -n "$CC_SRC" -c '{"function":"CommitWindow:GetCommitment","Args":["1"]}'
echo "GetCommitment exit=$?"

step "5) Anchor [build payload + invoke]"
PAY="$(node "$HERE/make_anchor_payload.js" "$SRC_CH" 1 0 99 100 "$QUORUM" "$KEY0" "$KEY1")"
CMT="$(echo "$PAY" | sed -n 1p)"; ENDO="$(echo "$PAY" | sed -n 2p)"
"${INVOKE[@]}" -C "$COORD_CH" -n "$CC_COORD" \
  -c "$(jq -nc --arg c "$CMT" --arg e "$ENDO" '{function:"Anchor:Anchor",Args:[$c,$e]}')" --waitForEvent
echo "Anchor exit=$?"

step "6) GetAnchors [query]"
peer chaincode query -C "$COORD_CH" -n "$CC_COORD" \
  -c "$(jq -nc --arg s "$SRC_CH" '{function:"Anchor:GetAnchors",Args:[$s]}')"
echo "GetAnchors exit=$?"
echo; echo "DIAG DONE"
