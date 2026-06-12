'use strict';
/*
 * local_crypto_bench.js -- crypto-only micro-benchmark on the LOCAL host.
 *
 * IMPORTANT: this is NOT the Fabric testbed measurement. It times the pure
 * Merkle/commitment primitives on whatever machine runs it, to validate the
 * O(N) build / complexity TREND only. The paper's per-operation Fabric latency
 * (Table 2) must come from bench_fabric.js on a real network. Do not paste
 * these numbers into the Fabric latency table.
 *
 * Run: node bench/local_crypto_bench.js
 */
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { performance } = require('perf_hooks');
const proto = require('../chaincode/lib/protocol');

const SALT = Buffer.from('per-channel-salt-key-known-to-source-members-only');

function mkEvents(n) {
  const evs = [];
  for (let i = 0; i < n; i++) {
    evs.push({ eid: `tx-${i}`, height: i, txIndex: 0,
               sourceDomain: 'domain-a-channel',
               payload: Buffer.from(`payload-${i}`), relevant: true });
  }
  return evs;
}

function bench(fn, iters, warmup) {
  for (let i = 0; i < warmup; i++) fn();
  const t = [];
  for (let i = 0; i < iters; i++) {
    const s = performance.now(); fn(); t.push(performance.now() - s);
  }
  t.sort((a, b) => a - b);
  return { median_ms: t[Math.floor(t.length / 2)],
           p95_ms: t[Math.floor(0.95 * t.length)] };
}

const rows = [];
for (const N of [10, 100, 1000]) {
  const evs = mkEvents(N);
  const r = bench(() => proto.windowRoot(SALT, evs), 200, 20);
  rows.push({ N, ...r });
}
const out = {
  host_note: 'LOCAL reference host -- NOT the Fabric testbed. Complexity-trend only.',
  node_version: process.version,
  windowRoot_build: rows,
};
const p = path.join(__dirname, 'local_crypto_trend.json');
fs.writeFileSync(p, JSON.stringify(out, null, 2));
console.log('windowRoot build (local host, NOT Fabric):');
for (const r of rows) console.log(`  N=${r.N}: median ${r.median_ms.toFixed(4)} ms`);
console.log('wrote', p);
