'use strict';
/*
 * bench_fabric.js -- end-to-end latency harness for the DEPLOYED protocol.
 *
 * This measures the paper's Table 2 latency rows on a REAL Fabric network. It
 * cannot run without a deployed network + gateway connection, so out of the box
 * it writes "TO_BE_MEASURED". Fill it by:
 *   1. bring up the network and deploy chaincode (see network/README.md)
 *   2. set the env vars below to your gateway/connection profile
 *   3. run: node bench/bench_fabric.js --iterations 100 --warmup 10
 *
 * It uses @hyperledger/fabric-gateway and perf_hooks (monotonic clock).
 * Measured operations:
 *   - CommitWindow (source chaincode) vs events-per-window N
 *   - Anchor       (coordination chaincode) validation latency
 *   - GetAnchors + off-chain verify() latency
 *
 * NOTE: median + p95 are reported over `iterations` after `warmup` discarded.
 */
const fs = require('fs');
const path = require('path');
const { performance } = require('perf_hooks');

const OUT = path.join(__dirname, 'bench_results.json');

function placeholderResults() {
  return {
    environment: 'TO_BE_MEASURED (record CPU, RAM, OS, Fabric version, Node version)',
    iterations: 'TO_BE_MEASURED',
    warmup: 'TO_BE_MEASURED',
    operations: {
      'CommitWindow N=10': { median_ms: 'TO_BE_MEASURED', p95_ms: 'TO_BE_MEASURED' },
      'CommitWindow N=100': { median_ms: 'TO_BE_MEASURED', p95_ms: 'TO_BE_MEASURED' },
      'CommitWindow N=1000': { median_ms: 'TO_BE_MEASURED', p95_ms: 'TO_BE_MEASURED' },
      'Anchor validate': { median_ms: 'TO_BE_MEASURED', p95_ms: 'TO_BE_MEASURED' },
      'GetAnchors + verify': { median_ms: 'TO_BE_MEASURED', p95_ms: 'TO_BE_MEASURED' },
    },
  };
}

async function measureOnFabric() {
  // ---- intentionally guarded: only runs if a gateway is configured ----
  if (!process.env.FABRIC_GATEWAY_ENDPOINT) {
    throw new Error('no gateway configured');
  }
  // Pseudocode wiring (uncomment and complete once your network is up):
  //
  // const { connect, signers } = require('@hyperledger/fabric-gateway');
  // const grpc = require('@grpc/grpc-js');
  // ... build identity + signer from MSP material ...
  // const gateway = connect({ client, identity, signer });
  // const sourceNet = gateway.getNetwork('domain-a-channel');
  // const commit = sourceNet.getContract('commitWindow');
  // for each N in [10,100,1000]:
  //     warmup, then time `commit.submitTransaction('CommitWindow', ...)`
  // const coordNet = gateway.getNetwork('coordination-channel');
  // const anchor = coordNet.getContract('anchor');
  //     time `anchor.submitTransaction('Anchor', cmtJson, endoJson)`
  //     time `anchor.evaluateTransaction('GetAnchors', src)` + local verify()
  //
  // Aggregate median/p95 with the helper below.
  throw new Error('gateway wiring not completed -- see comments');
}

function summarise(samples) {
  const s = samples.slice().sort((a, b) => a - b);
  const q = (p) => s[Math.min(s.length - 1, Math.floor(p * s.length))];
  return { median_ms: q(0.5), p95_ms: q(0.95) };
}

(async () => {
  let results;
  try {
    results = await measureOnFabric();
  } catch (e) {
    console.error(`[bench_fabric] not run on Fabric (${e.message}); `
                + 'emitting TO_BE_MEASURED placeholders.');
    results = placeholderResults();
  }
  fs.writeFileSync(OUT, JSON.stringify(results, null, 2));
  console.log('wrote', OUT);
})();

module.exports = { summarise };
