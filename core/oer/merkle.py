"""Events, salted content-hiding leaves, and Merkle roots.

Implements Definition 1 (window commitment) and Algorithm 2 (Merkle root with
identity-bound leaves) from the paper.

Confidentiality note: the raw event payload never enters a leaf. The leaf binds
SHA-256(payload) under a PRF-derived salt, so a verifier that lacks the
per-channel salt key learns nothing about payload contents from the leaf.
"""
from __future__ import annotations
from dataclasses import dataclass
import hmac

from .encoding import enc_uint, enc_str, enc_bytes, sha256


@dataclass(frozen=True)
class Event:
    """A ledger event on a source channel.

    Only events with relevant=True are cross-domain-relevant and enter a
    window commitment. `payload` is opaque/confidential bytes; it is committed
    only via its hash.
    """
    eid: str            # unique event id (e.g., Fabric txId)
    height: int         # block height on the source channel
    tx_index: int       # transaction index within the block
    source_domain: str  # logical domain / channel id
    payload: bytes      # opaque, confidential content
    relevant: bool      # rho_s(e): is this event cross-domain-relevant?


def canonical_order(events: list[Event]) -> list[Event]:
    """Canonical ordering: ascending (height, tx_index). Total order because
    (height, tx_index) uniquely identifies a transaction position."""
    return sorted(events, key=lambda e: (e.height, e.tx_index))


def event_bytes(e: Event) -> bytes:
    """serialize(event): fixed field order, length-prefixed. payload enters
    only as its SHA-256 commitment."""
    payload_commit = sha256(e.payload)
    return (
        enc_str(e.eid)
        + enc_uint(e.height)
        + enc_uint(e.tx_index)
        + enc_str(e.source_domain)
        + enc_bytes(payload_commit)
    )


def salt(salt_key: bytes, eid: str) -> bytes:
    """salt(e) = HMAC-SHA256(k_s, eid). Deterministic across honest peers
    (same key), unpredictable to a verifier without k_s."""
    return hmac.new(salt_key, eid.encode("utf-8"), "sha256").digest()


def leaf(salt_key: bytes, e: Event) -> bytes:
    """leaf(e) = SHA-256( salt(e) || serialize(event) )."""
    return sha256(salt(salt_key, e.eid) + event_bytes(e))


def merkle_root(leaves: list[bytes]) -> bytes:
    """Algorithm 2 Merkle root. Odd levels duplicate the last node.
    Empty set commits to SHA-256(b'')."""
    if not leaves:
        return sha256(b"")
    level = list(leaves)
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else level[i]
            nxt.append(sha256(left + right))
        level = nxt
    return level[0]


def window_root(salt_key: bytes, events: list[Event]) -> tuple[bytes, int]:
    """Compute (root, count) over the cross-domain-relevant events of a window,
    in canonical order. Returns the Merkle root and the relevant-event count."""
    relevant = [e for e in canonical_order(events) if e.relevant]
    leaves = [leaf(salt_key, e) for e in relevant]
    return merkle_root(leaves), len(relevant)
