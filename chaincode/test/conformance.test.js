'use strict';
// Cross-language conformance: the Node protocol library must reproduce the
// canonical vectors emitted by the Python reference (experiments/gen_vectors.py).
// Run: node chaincode/test/conformance.test.js
// Exits non-zero on any mismatch.
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const proto = require('../lib/protocol');

const vpath = path.join(__dirname, '..', '..', 'vectors', 'conformance.json');
const v = JSON.parse(fs.readFileSync(vpath, 'utf8'));
const saltKey = Buffer.from(v.salt_key_utf8, 'utf8');

let checks = 0;

// empty root
assert.strictEqual(proto.merkleRoot([]).toString('hex'), v.empty_root_hex,
  'empty Merkle root mismatch');
checks++;

// per-event leaves
const events = v.events.map((e) => ({
  eid: e.eid, height: e.height, txIndex: e.tx_index,
  sourceDomain: e.source_domain, payload: Buffer.from(e.payload_utf8, 'utf8'),
  relevant: e.relevant,
}));
for (let i = 0; i < events.length; i++) {
  const got = proto.leaf(saltKey, events[i]).toString('hex');
  assert.strictEqual(got, v.events[i].leaf_hex,
    `leaf mismatch for ${events[i].eid}`);
  checks++;
}

// window root + count
const wr = proto.windowRoot(saltKey, events);
assert.strictEqual(wr.root.toString('hex'), v.window_root_hex,
  'window root mismatch');
assert.strictEqual(wr.count, v.window_count, 'window count mismatch');
checks += 2;

// commitment bytes
const c = {
  sourceChannel: v.commitment.source_channel, w: v.commitment.w,
  a: v.commitment.a, b: v.commitment.b,
  root: Buffer.from(v.commitment.root_hex, 'hex'), count: v.commitment.count,
};
assert.strictEqual(proto.commitmentBytes(c).toString('hex'),
  v.commitment.commitment_bytes_hex, 'commitment bytes mismatch');
checks++;

console.log(`conformance: ${checks} checks PASSED (Node matches Python vectors)`);
console.log('window_root:', wr.root.toString('hex'));
