'use strict';
// Deterministic, length-prefixed canonical encoding -- Node mirror of
// core/oer/encoding.py. MUST stay byte-for-byte identical. Verified by
// chaincode/test/conformance.test.js against Python-generated vectors.
const crypto = require('crypto');

function encUint(n) {
  // 8-byte big-endian unsigned integer
  const b = Buffer.alloc(8);
  b.writeBigUInt64BE(BigInt(n));
  return b;
}
function encBytes(b) {
  return Buffer.concat([encUint(b.length), b]);
}
function encStr(s) {
  return encBytes(Buffer.from(s, 'utf8'));
}
function sha256(b) {
  return crypto.createHash('sha256').update(b).digest();
}

module.exports = { encUint, encBytes, encStr, sha256 };
