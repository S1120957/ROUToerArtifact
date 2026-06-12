"""Window commitments and simulated source-channel endorsement.

In a real Fabric deployment, the commitment tuple is produced by the
`CommitWindow` chaincode and endorsed under the source channel's endorsement
policy P_s (MSP signatures collected from a quorum of source peers). Here we
model endorsement faithfully but with HMAC "signatures" under per-peer keys, so
that the security argument is concrete: an adversary that controls only a
sub-quorum of peers cannot produce a valid endorsement for a commitment that
the honest quorum did not compute.

This is the source-AUTHORITATIVE attestation that Proposition 1 (necessity)
requires: the completeness reference is bound to the source channel, not to the
coordinator.
"""
from __future__ import annotations
from dataclasses import dataclass
import hmac

from .encoding import enc_uint, enc_str, enc_bytes


@dataclass(frozen=True)
class Commitment:
    """Cmt = (source_channel, w, [a, b], root, count).  (Definition 1)"""
    source_channel: str
    w: int               # window index (1-based)
    a: int               # window start height (inclusive)
    b: int               # window end height (inclusive)
    root: bytes          # Merkle root over relevant events
    count: int           # number of relevant events


def commitment_bytes(c: Commitment) -> bytes:
    """Canonical bytes of a commitment, used as the signing pre-image."""
    return (
        enc_str(c.source_channel)
        + enc_uint(c.w)
        + enc_uint(c.a)
        + enc_uint(c.b)
        + enc_bytes(c.root)
        + enc_uint(c.count)
    )


@dataclass(frozen=True)
class EndorsementPolicy:
    """A t-of-n policy over named source-channel peers."""
    members: tuple[str, ...]   # peer ids authorised on this channel
    quorum: int                # minimum distinct valid signatures required


def peer_sign(peer_key: bytes, c: Commitment) -> bytes:
    """A single peer's endorsement signature over the commitment."""
    return hmac.new(peer_key, commitment_bytes(c), "sha256").digest()


def endorse(c: Commitment, peer_keys: dict[str, bytes],
            signers: list[str]) -> dict[str, bytes]:
    """Collect signatures from `signers` (a subset of peers holding keys)."""
    return {p: peer_sign(peer_keys[p], c) for p in signers}


def endorsement_valid(c: Commitment, endorsement: dict[str, bytes],
                      policy: EndorsementPolicy,
                      peer_keys: dict[str, bytes]) -> bool:
    """True iff `endorsement` contains >= quorum distinct, valid signatures
    from authorised members over exactly this commitment `c`."""
    good = 0
    seen = set()
    for peer, sig in endorsement.items():
        if peer in seen or peer not in policy.members or peer not in peer_keys:
            continue
        expected = peer_sign(peer_keys[peer], c)
        if hmac.compare_digest(expected, sig):
            seen.add(peer)
            good += 1
    return good >= policy.quorum
