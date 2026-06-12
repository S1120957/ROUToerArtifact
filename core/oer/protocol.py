"""On-chain anchor validation and the off-chain verifier.

`AnchorContract` mirrors the coordination-channel chaincode `Anchor` (see
chaincode/coordination/anchor.js): it enforces, at commit time, valid source
endorsement + strict window monotonicity + height contiguity. It REJECTS at
commit time, so an invalid anchor never enters the ledger.

`verify()` mirrors the off-chain verifier that reads ONLY the coordination
channel. It re-checks the committed sequence (defense in depth) and performs
the freshness/truncation check that on-chain validation alone cannot (because
truncation is the ABSENCE of an anchor).
"""
from __future__ import annotations
from dataclasses import dataclass

from .commitment import Commitment, EndorsementPolicy, endorsement_valid


class AnchorReject(Exception):
    """Raised by AnchorContract.anchor() when validation fails. The `reason`
    string is the machine-checkable rejection code."""
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass
class AnchorRecord:
    """What is persisted on the coordination channel per accepted anchor."""
    commitment: Commitment
    endorsement: dict[str, bytes]
    coord_height: int        # coordination-channel block height at commit


class AnchorContract:
    """Coordination-channel state machine. One instance models one channel."""

    def __init__(self, policies: dict[str, EndorsementPolicy],
                 peer_keys: dict[str, dict[str, bytes]]):
        # per-source-channel endorsement policy and authorised peer keys
        self.policies = policies
        self.peer_keys = peer_keys
        # committed log and per-source last (w, b, coord_height)
        self.log: list[AnchorRecord] = []
        self._last: dict[str, tuple[int, int, int]] = {}

    def anchor(self, c: Commitment, endorsement: dict[str, bytes],
               coord_height: int) -> AnchorRecord:
        """Algorithm: Anchor(Cmt, endorsement). Raises AnchorReject on failure;
        on success appends to the committed log and returns the record."""
        s = c.source_channel
        if s not in self.policies:
            raise AnchorReject("unknown-source-channel")

        if not endorsement_valid(c, endorsement, self.policies[s],
                                 self.peer_keys[s]):
            raise AnchorReject("bad-endorsement")

        if s not in self._last:
            if c.w != 1:
                raise AnchorReject("expected-window-1")
        else:
            last_w, last_b, _ = self._last[s]
            if c.w != last_w + 1:
                raise AnchorReject("non-monotonic-window")
            if c.a != last_b + 1:
                raise AnchorReject("non-contiguous-height")

        rec = AnchorRecord(commitment=c, endorsement=dict(endorsement),
                           coord_height=coord_height)
        self.log.append(rec)
        self._last[s] = (c.w, c.b, coord_height)
        return rec


@dataclass
class VerifyResult:
    accepted: bool
    reason: str = "ok"
    source_channel: str = ""
    window: int = 0


def verify(anchor_log: list[AnchorRecord],
           policies: dict[str, EndorsementPolicy],
           peer_keys: dict[str, dict[str, bytes]],
           delta: int,
           coord_frontier_height: int) -> VerifyResult:
    """Verifier with read access ONLY to the coordination channel.

    Checks per source channel:
      (1) every anchor carries a valid source endorsement
      (2) window indices are 1,2,3,... contiguous (no interior gap, no replay)
      (3) height ranges are contiguous and non-overlapping
      (4) freshness: the latest anchor is within `delta` coordination blocks of
          the current frontier (else tail truncation -> detectable stall)
    Returns accepted=True only if all checks pass for all source channels.
    """
    by_source: dict[str, list[AnchorRecord]] = {}
    for rec in anchor_log:
        by_source.setdefault(rec.commitment.source_channel, []).append(rec)

    for s, recs in by_source.items():
        # (1) endorsements
        for rec in recs:
            if not endorsement_valid(rec.commitment, rec.endorsement,
                                     policies[s], peer_keys[s]):
                return VerifyResult(False, "bad-endorsement", s,
                                    rec.commitment.w)
        # (2) contiguous window indices starting at 1
        for i, rec in enumerate(recs):
            if rec.commitment.w != i + 1:
                return VerifyResult(False, "window-gap-or-replay", s,
                                    rec.commitment.w)
        # (3) contiguous heights
        for i in range(1, len(recs)):
            if recs[i].commitment.a != recs[i - 1].commitment.b + 1:
                return VerifyResult(False, "non-contiguous-height", s,
                                    recs[i].commitment.w)
        # (4) freshness / truncation
        last_coord_h = recs[-1].coord_height
        if coord_frontier_height - last_coord_h > delta:
            return VerifyResult(False, "stale-frontier", s, recs[-1].commitment.w)

    return VerifyResult(True, "ok")
