'use strict';
// Pure protocol logic shared by the source and coordination chaincode.
// Node mirror of core/oer/merkle.py + the anchor predicate in protocol.py.
// No Fabric dependency here, so it can be unit/conformance-tested standalone.
const crypto = require('crypto');
const { encUint, encBytes, encStr, sha256 } = require('./encoding');

// event = { eid, height, txIndex, sourceDomain, payload(Buffer), relevant(bool) }

function eventBytes(e) {
  const payloadCommit = sha256(Buffer.isBuffer(e.payload) ? e.payload
                                                          : Buffer.from(e.payload));
  return Buffer.concat([
    encStr(e.eid),
    encUint(e.height),
    encUint(e.txIndex),
    encStr(e.sourceDomain),
    encBytes(payloadCommit),
  ]);
}

function salt(saltKey, eid) {
  return crypto.createHmac('sha256', saltKey).update(eid, 'utf8').digest();
}

function leaf(saltKey, e) {
  return sha256(Buffer.concat([salt(saltKey, e.eid), eventBytes(e)]));
}

function canonicalOrder(events) {
  return events.slice().sort((x, y) =>
    x.height - y.height || x.txIndex - y.txIndex);
}

function merkleRoot(leaves) {
  if (leaves.length === 0) return sha256(Buffer.alloc(0));
  let level = leaves.slice();
  while (level.length > 1) {
    const next = [];
    for (let i = 0; i < level.length; i += 2) {
      const l = level[i];
      const r = i + 1 < level.length ? level[i + 1] : level[i];
      next.push(sha256(Buffer.concat([l, r])));
    }
    level = next;
  }
  return level[0];
}

function windowRoot(saltKey, events) {
  const relevant = canonicalOrder(events).filter((e) => e.relevant);
  const leaves = relevant.map((e) => leaf(saltKey, e));
  return { root: merkleRoot(leaves), count: relevant.length };
}

// commitment = { sourceChannel, w, a, b, root(Buffer), count }
function commitmentBytes(c) {
  return Buffer.concat([
    encStr(c.sourceChannel),
    encUint(c.w),
    encUint(c.a),
    encUint(c.b),
    encBytes(c.root),
    encUint(c.count),
  ]);
}

// Pure anchor predicate (the monotonic + contiguity part enforced on-chain).
// `last` is {w, b} for this source channel, or null if none yet.
function checkMonotonicContiguous(last, c) {
  if (last === null || last === undefined) {
    if (c.w !== 1) return { ok: false, reason: 'expected-window-1' };
    return { ok: true, reason: 'ok' };
  }
  if (c.w !== last.w + 1) return { ok: false, reason: 'non-monotonic-window' };
  if (c.a !== last.b + 1) return { ok: false, reason: 'non-contiguous-height' };
  return { ok: true, reason: 'ok' };
}

module.exports = {
  eventBytes, salt, leaf, canonicalOrder, merkleRoot, windowRoot,
  commitmentBytes, checkMonotonicContiguous,
};
