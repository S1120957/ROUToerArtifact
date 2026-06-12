'use strict';
/*
 * Anchor -- coordination-channel chaincode.
 *
 * Enforces, at commit time (paper Alg. 2 / Section "Construction"):
 *   (i)   the source endorsement over the commitment is valid under P_s;
 *   (ii)  window indices per source are strictly monotone (anti-replay);
 *   (iii) height ranges per source are contiguous (no skipped interior window).
 * A commitment that fails any check is REJECTED and never enters the ledger.
 *
 * The off-chain verifier reads GetAnchors (and only the coordination channel)
 * and additionally applies the freshness deadline to catch tail truncation.
 *
 * Endorsement verification (TRL-4 prototype):
 *   The coordination channel holds a registry of each source channel's
 *   verification keys + quorum (RegisterSourcePolicy). Anchor verifies that the
 *   embedded signatures meet quorum over the canonical commitment bytes.
 *   For reproducibility the prototype uses HMAC verification keys identical to
 *   the reference simulator; PRODUCTION wires this to source MSP ECDSA certs
 *   (verifying another channel's endorsement requires the source MSP material,
 *   distributed here via the on-chain registry). This is the one place that
 *   must be replaced for a real multi-MSP deployment; the monotonic+contiguity
 *   logic is unchanged.
 */
const crypto = require('crypto');
const { Contract } = require('fabric-contract-api');
const proto = require('../lib/protocol');

const POL_PREFIX = 'pol:';   // pol:<sourceChannel> -> {members:[{id,keyHex}], quorum}
const ANC_PREFIX = 'anc:';   // anc:<sourceChannel>:<w(12)> -> anchor record
const LAST_PREFIX = 'last:'; // last:<sourceChannel> -> {w,b,coordHeight}

function commitmentBytesFromJson(c) {
  return proto.commitmentBytes({
    sourceChannel: c.sourceChannel, w: c.w, a: c.a, b: c.b,
    root: Buffer.from(c.rootHex, 'hex'), count: c.count,
  });
}

function endorsementValid(c, endorsement, policy) {
  // endorsement: { peerId: sigHex }. HMAC prototype (see header note).
  const msg = commitmentBytesFromJson(c);
  const members = new Map(policy.members.map((m) => [m.id, m.keyHex]));
  let good = 0; const seen = new Set();
  for (const [peer, sigHex] of Object.entries(endorsement)) {
    if (seen.has(peer) || !members.has(peer)) continue;
    const key = Buffer.from(members.get(peer), 'hex');
    const expect = crypto.createHmac('sha256', key).update(msg).digest('hex');
    if (crypto.timingSafeEqual(Buffer.from(expect, 'hex'),
                               Buffer.from(sigHex, 'hex'))) {
      seen.add(peer); good++;
    }
  }
  return good >= policy.quorum;
}

class Anchor extends Contract {

  // Register a source channel's endorsement policy + verification keys.
  // policyJson = {members:[{id, keyHex}], quorum}
  async RegisterSourcePolicy(ctx, sourceChannel, policyJson) {
    JSON.parse(policyJson); // validate
    await ctx.stub.putState(`${POL_PREFIX}${sourceChannel}`,
      Buffer.from(policyJson));
    return 'ok';
  }

  // Anchor one endorsed commitment relayed by the (untrusted) coordinator.
  // commitmentJson = {sourceChannel,w,a,b,rootHex,count}
  // endorsementJson = {peerId: sigHex, ...}
  async Anchor(ctx, commitmentJson, endorsementJson) {
    const c = JSON.parse(commitmentJson);
    const endorsement = JSON.parse(endorsementJson);

    const polRaw = await ctx.stub.getState(`${POL_PREFIX}${c.sourceChannel}`);
    if (!polRaw || polRaw.length === 0) throw new Error('unknown-source-channel');
    const policy = JSON.parse(polRaw.toString());

    if (!endorsementValid(c, endorsement, policy)) {
      throw new Error('bad-endorsement');
    }

    const lastRaw = await ctx.stub.getState(`${LAST_PREFIX}${c.sourceChannel}`);
    const last = (lastRaw && lastRaw.length) ? JSON.parse(lastRaw.toString()) : null;
    const chk = proto.checkMonotonicContiguous(last, c);
    if (!chk.ok) throw new Error(chk.reason);

    // coordination block height at commit (used by the freshness check)
    const coordHeight = parseInt(ctx.stub.getTxTimestamp().seconds.toString(), 10);
    const rec = { commitment: c, endorsement, coordHeight };
    const key = `${ANC_PREFIX}${c.sourceChannel}:${String(c.w).padStart(12, '0')}`;
    await ctx.stub.putState(key, Buffer.from(JSON.stringify(rec)));
    await ctx.stub.putState(`${LAST_PREFIX}${c.sourceChannel}`,
      Buffer.from(JSON.stringify({ w: c.w, b: c.b, coordHeight })));
    ctx.stub.setEvent('AnchorCommitted', Buffer.from(JSON.stringify(rec)));
    return JSON.stringify(rec);
  }

  // Verifier read path: the full anchor sequence for a source channel.
  async GetAnchors(ctx, sourceChannel) {
    const start = `${ANC_PREFIX}${sourceChannel}:`;
    const end = `${ANC_PREFIX}${sourceChannel}:~`;
    const iter = await ctx.stub.getStateByRange(start, end);
    const out = [];
    for await (const kv of iter) out.push(JSON.parse(kv.value.toString()));
    return JSON.stringify(out);
  }
}

module.exports = Anchor;
module.exports.contracts = [Anchor];
