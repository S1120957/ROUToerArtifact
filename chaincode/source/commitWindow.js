'use strict';
/*
 * CommitWindow -- source-channel chaincode.
 *
 * Runs on a source channel C_s and produces the per-window salted-Merkle
 * commitment that is the source-authoritative attestation of that channel's
 * cross-domain-relevant event set (paper Section "Construction", Alg. 1).
 *
 * Trust model: this transaction is endorsed under the source channel's
 * endorsement policy P_s, so the committed root is attested by an honest
 * quorum of source peers -- NOT by the coordinator. Determinism (same world
 * state + same salt key + canonical ordering) guarantees every honest endorser
 * computes the identical root, so P_s is satisfiable only on the true root.
 *
 * Prototype notes (TRL-4):
 *  - The cross-domain-relevant event index is maintained on-channel via
 *    RecordEvent. In production this index is derivable from block history;
 *    we keep an explicit index for reproducibility and clarity.
 *  - The per-channel salt key k_s is supplied via TRANSIENT data by an
 *    authorised source-org client and is NEVER written to the ledger. In
 *    production it lives in an HSM/TEE (paper DC-4 discussion).
 */
const { Contract } = require('fabric-contract-api');
const proto = require('../lib/protocol');

const IDX_PREFIX = 'evt:';   // evt:<height>:<txIndex> -> event metadata
const CMT_PREFIX = 'cmt:';   // cmt:<w> -> committed commitment tuple
const LASTW_KEY = 'lastWindow';

class CommitWindow extends Contract {

  // Record one cross-domain-relevant event into the on-channel index.
  // payload is passed via transient ('payload'); only its commitment is stored.
  async RecordEvent(ctx, eid, height, txIndex, sourceDomain) {
    const t = ctx.stub.getTransient();
    const payload = t.has('payload') ? t.get('payload') : Buffer.alloc(0);
    const payloadCommit = proto.sha256
      ? require('../lib/encoding').sha256(payload)
      : payload;
    const rec = {
      eid, height: Number(height), txIndex: Number(txIndex), sourceDomain,
      payloadCommitHex: payloadCommit.toString('hex'), relevant: true,
    };
    const key = `${IDX_PREFIX}${String(height).padStart(12, '0')}:${String(txIndex).padStart(6, '0')}`;
    await ctx.stub.putState(key, Buffer.from(JSON.stringify(rec)));
    return JSON.stringify(rec);
  }

  // Deterministically compute and store the commitment for window w over
  // height range [a, b]. Salt key supplied via transient ('saltKey').
  async CommitWindow(ctx, sourceChannel, w, a, b) {
    w = Number(w); a = Number(a); b = Number(b);
    const t = ctx.stub.getTransient();
    if (!t.has('saltKey')) throw new Error('saltKey transient required');
    const saltKey = t.get('saltKey');

    // range-scan the relevant-event index over [a, b]
    const start = `${IDX_PREFIX}${String(a).padStart(12, '0')}:`;
    const end = `${IDX_PREFIX}${String(b).padStart(12, '0')}:~`;
    const iter = await ctx.stub.getStateByRange(start, end);
    const events = [];
    for await (const kv of iter) {
      const r = JSON.parse(kv.value.toString());
      events.push({
        eid: r.eid, height: r.height, txIndex: r.txIndex,
        sourceDomain: r.sourceDomain,
        // leaf binds sha256(payload); we already stored that commit, so feed
        // it back through eventBytes by reconstructing the same preimage.
        payload: Buffer.from(r.payloadCommitHex, 'hex'),
        relevant: r.relevant,
        _precommitted: true,
      });
    }
    // NOTE: because payloadCommit is already a hash, we must NOT hash it again.
    // Use the precommitted-aware leaf path:
    const relevant = proto.canonicalOrder(events).filter((e) => e.relevant);
    const enc = require('../lib/encoding');
    const leaves = relevant.map((e) => {
      const evBytes = Buffer.concat([
        enc.encStr(e.eid), enc.encUint(e.height), enc.encUint(e.txIndex),
        enc.encStr(e.sourceDomain), enc.encBytes(e.payload),  // already a commit
      ]);
      return enc.sha256(Buffer.concat([proto.salt(saltKey, e.eid), evBytes]));
    });
    const root = proto.merkleRoot(leaves);
    const count = relevant.length;

    const cmt = {
      sourceChannel, w, a, b, rootHex: root.toString('hex'), count,
    };
    await ctx.stub.putState(`${CMT_PREFIX}${w}`, Buffer.from(JSON.stringify(cmt)));
    await ctx.stub.putState(LASTW_KEY, Buffer.from(JSON.stringify({ w, b })));
    return JSON.stringify(cmt);
  }

  async GetCommitment(ctx, w) {
    const v = await ctx.stub.getState(`${CMT_PREFIX}${Number(w)}`);
    if (!v || v.length === 0) throw new Error(`no commitment for window ${w}`);
    return v.toString();
  }
}

module.exports = CommitWindow;
module.exports.contracts = [CommitWindow];
