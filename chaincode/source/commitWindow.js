'use strict';
const { Contract } = require('fabric-contract-api');
const proto = require('../lib/protocol');

const IDX_PREFIX = 'evt:';
const CMT_PREFIX = 'cmt:';
const LASTW_KEY = 'lastWindow';

class CommitWindow extends Contract {

  async RecordEvent(ctx, eid, height, txIndex, sourceDomain) {
    const t = ctx.stub.getTransient();
    const payload = t.has('payload') ? t.get('payload') : Buffer.alloc(0);
    const payloadCommit = require('../lib/encoding').sha256(payload);
    const rec = {
      eid, height: Number(height), txIndex: Number(txIndex), sourceDomain,
      payloadCommitHex: payloadCommit.toString('hex'), relevant: true,
    };
    const key = `${IDX_PREFIX}${String(height).padStart(12, '0')}:${String(txIndex).padStart(6, '0')}`;
    await ctx.stub.putState(key, Buffer.from(JSON.stringify(rec)));
    return JSON.stringify(rec);
  }

  async CommitWindow(ctx, sourceChannel, w, a, b) {
    w = Number(w); a = Number(a); b = Number(b);
    const t = ctx.stub.getTransient();
    if (!t.has('saltKey')) throw new Error('saltKey transient required');
    const saltKey = t.get('saltKey');

    const start = `${IDX_PREFIX}${String(a).padStart(12, '0')}:`;
    const end = `${IDX_PREFIX}${String(b).padStart(12, '0')}:~`;
    const iter = await ctx.stub.getStateByRange(start, end);
    const events = [];
    let res = await iter.next();
    while (!res.done) {
      const r = JSON.parse(res.value.value.toString());
      events.push({
        eid: r.eid, height: r.height, txIndex: r.txIndex,
        sourceDomain: r.sourceDomain,
        payload: Buffer.from(r.payloadCommitHex, 'hex'),
        relevant: r.relevant,
        _precommitted: true,
      });
      res = await iter.next();
    }
    await iter.close();

    const relevant = proto.canonicalOrder(events).filter((e) => e.relevant);
    const enc = require('../lib/encoding');
    const leaves = relevant.map((e) => {
      const evBytes = Buffer.concat([
        enc.encStr(e.eid), enc.encUint(e.height), enc.encUint(e.txIndex),
        enc.encStr(e.sourceDomain), enc.encBytes(e.payload),
      ]);
      return enc.sha256(Buffer.concat([proto.salt(saltKey, e.eid), evBytes]));
    });
    const root = proto.merkleRoot(leaves);
    const count = relevant.length;

    const cmt = { sourceChannel, w, a, b, rootHex: root.toString('hex'), count };
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
