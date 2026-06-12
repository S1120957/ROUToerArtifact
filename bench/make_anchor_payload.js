'use strict';
/*
 * make_anchor_payload.js -- emit a well-formed (commitment, endorsement) pair
 * for window w so the Anchor chaincode ACCEPTS it, for latency benchmarking.
 *
 * The endorsement is a quorum of HMACs over the canonical commitment bytes,
 * under keys that MUST match those registered via RegisterSourcePolicy in
 * bench_fabric_cli.sh. The Merkle root is a deterministic dummy: Anchor does
 * not recompute it, so its value does not affect the accept-path latency we
 * are measuring.
 *
 * Usage: node make_anchor_payload.js <srcChannel> <w> <a> <b> <count> <quorum> <key0hex> <key1hex> ...
 * Prints two lines: compact-JSON commitment, then compact-JSON endorsement.
 */
const crypto = require('crypto');
const proto = require('../chaincode/lib/protocol');

const [, , sourceChannel, wS, aS, bS, countS, quorumS, ...keyHex] = process.argv;
const w = Number(wS), a = Number(aS), b = Number(bS);
const count = Number(countS), quorum = Number(quorumS);

if (!sourceChannel || Number.isNaN(w) || keyHex.length < quorum) {
  console.error('usage: node make_anchor_payload.js <srcChannel> <w> <a> <b> <count> <quorum> <key0hex> ...');
  process.exit(1);
}

const root = crypto.createHash('sha256').update(`root-${w}`).digest();
const commitment = { sourceChannel, w, a, b, rootHex: root.toString('hex'), count };
const msg = proto.commitmentBytes({ sourceChannel, w, a, b, root, count });

const endorsement = {};
for (let i = 0; i < quorum; i++) {
  const key = Buffer.from(keyHex[i], 'hex');
  endorsement[`peer${i}`] = crypto.createHmac('sha256', key).update(msg).digest('hex');
}

process.stdout.write(JSON.stringify(commitment) + '\n');
process.stdout.write(JSON.stringify(endorsement) + '\n');
