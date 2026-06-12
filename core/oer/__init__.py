"""Omission-Evident Reconciliation (OER) reference simulator.

Pure-Python, stdlib-only reference implementation of the salted-Merkle +
endorsed-window-binding protocol. Deterministic; produces the security
(omission-detection) results that the paper reports. No Fabric required.
"""
from .merkle import Event, window_root, merkle_root, leaf
from .commitment import (Commitment, EndorsementPolicy, endorse,
                         endorsement_valid)
from .protocol import AnchorContract, AnchorReject, AnchorRecord, verify, VerifyResult

__all__ = [
    "Event", "window_root", "merkle_root", "leaf",
    "Commitment", "EndorsementPolicy", "endorse", "endorsement_valid",
    "AnchorContract", "AnchorReject", "AnchorRecord", "verify", "VerifyResult",
]
