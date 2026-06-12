'use strict';
/*
 * Per-anchor world-state size. This is DETERMINISTIC (it is the serialized byte
 * length of the persisted anchor record), so it is a real measurement, not a
 * Fabric-timing measurement. Reproducible on any host with Node.
 *
 * Run: node bench/storage_size.js
 * Emits bench/storage_results.json.
 */
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const proto = require('../chaincode/lib/protocol');

function anchorRecordBytes(sourceChannel, w, a, b, quorum) {
  const root = crypto.randomBytes(32);
  const c = { sourceChannel, w, a, b, rootHex: root.toString('hex'),
              count: 64 };
  // quorum HMAC-SHA256 signatures, 32 bytes each -> 64 hex chars
  const endorsement = {};
  for (let i = 0; i < quorum; i++) {
    endorsement[`peer${i}`] = crypto.randomBytes(32).toString('hex');
  }
  const rec = { commitment: c, endorsement, coordHeight: 1700000000 };
  return Buffer.byteLength(JSON.stringify(rec), 'utf8');
}

const rows = [];
for (const quorum of [1, 2, 3]) {
  const size = anchorRecordBytes('domain-a-channel', 1, 0, 1, quorum);
  rows.push({ sourceChannel: 'domain-a-channel', quorum, bytesPerAnchor: size });
}

// daily growth at one anchor per CDC window; the verifier stores nothing extra.
const out = {
  note: 'Deterministic serialized size of one persisted anchor record. '
      + 'Real, not Fabric-timing. Leaves are NOT stored (only the root), so '
      + 'size is O(1) per anchor, independent of events-per-window.',
  rows,
};
const p = path.join(__dirname, 'storage_results.json');
fs.writeFileSync(p, JSON.stringify(out, null, 2));
console.log('per-anchor world-state size (bytes):');
for (const r of rows) console.log(`  quorum ${r.quorum}: ${r.bytesPerAnchor} bytes`);
console.log('wrote', p);
