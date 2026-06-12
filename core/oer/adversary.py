"""Coordinators: one honest, six adversarial.

The coordinator is UNTRUSTED. Its only legitimate job is to relay endorsed
commitments from source channels to the coordination channel. Each adversarial
behaviour attempts to violate completeness; the battery (experiments/
run_security_battery.py) checks that each is detected -- either rejected at
commit time by AnchorContract, or flagged by verify().

An adversary controls the coordinator and a SUB-QUORUM of source peers
(adversary_signers). It therefore cannot produce a valid endorsement for any
commitment the honest quorum did not compute.
"""
from __future__ import annotations
from dataclasses import dataclass

from .merkle import Event, window_root
from .commitment import Commitment, endorse


@dataclass
class SourceWindow:
    """A source channel's honest window: the true relevant event set plus the
    honestly-computed, honestly-endorsed commitment."""
    commitment: Commitment
    endorsement: dict
    events: list  # the true events (adversary may try to tamper with these)


def build_honest_windows(source_channel: str, salt_key: bytes,
                         windows: list[tuple[int, int, list[Event]]],
                         peer_keys: dict, honest_signers: list[str]
                         ) -> list[SourceWindow]:
    """Construct honestly-endorsed commitments for a sequence of windows.

    `windows` is a list of (a, b, events). Window indices are assigned 1..N in
    order. Each commitment is signed by `honest_signers` (an honest quorum).
    """
    out = []
    for i, (a, b, events) in enumerate(windows, start=1):
        root, count = window_root(salt_key, events)
        c = Commitment(source_channel, i, a, b, root, count)
        endo = endorse(c, peer_keys, honest_signers)
        out.append(SourceWindow(c, endo, events))
    return out


# --- honest coordinator ----------------------------------------------------

def relay_honest(windows: list[SourceWindow]):
    """Yield (commitment, endorsement) in order, unchanged."""
    for sw in windows:
        yield sw.commitment, sw.endorsement


# --- adversarial coordinators ----------------------------------------------
# Each returns a list of (commitment, endorsement) the adversary tries to anchor.
# `adversary_signers` is the sub-quorum the adversary can sign with.

def attack_drop_within_window(windows, salt_key, peer_keys, adversary_signers):
    """Remove one event from a window and re-commit. The adversary must
    recompute the root and can only sign with its sub-quorum."""
    out = []
    for idx, sw in enumerate(windows):
        if idx == 1 and len(sw.events) > 1:
            tampered = sw.events[:-1]                       # drop one event
            root, count = window_root(salt_key, tampered)
            c = Commitment(sw.commitment.source_channel, sw.commitment.w,
                           sw.commitment.a, sw.commitment.b, root, count)
            endo = endorse(c, peer_keys, adversary_signers)  # sub-quorum only
            out.append((c, endo))
        else:
            out.append((sw.commitment, sw.endorsement))
    return out


def attack_reorder_within_window(windows, salt_key, peer_keys, adversary_signers):
    """Reorder events within a window (non-canonical). Changes the root ->
    requires re-signing -> adversary cannot reach quorum."""
    out = []
    for idx, sw in enumerate(windows):
        if idx == 1 and len(sw.events) > 1:
            reordered = list(reversed(sw.events))
            # force non-canonical order by tagging tx_index inversely is overkill;
            # window_root re-canonicalises, so to actually change the root we
            # swap two events' identities deterministically:
            ev = list(sw.events)
            ev[0], ev[-1] = ev[-1], ev[0]
            # rebuild with swapped heights to defeat canonical re-sort
            from .merkle import Event as E
            swapped = []
            for j, e in enumerate(ev):
                swapped.append(E(e.eid, e.height, e.tx_index, e.source_domain,
                                 e.payload, e.relevant))
            # Reordering alone cannot change a Merkle root if the verifier
            # re-canonicalises; the realistic attack is presenting a DIFFERENT
            # ordered leaf sequence. We model that by committing to the reversed
            # leaf order directly:
            from .merkle import leaf, merkle_root
            relevant = [e for e in reordered if e.relevant]
            leaves = [leaf(salt_key, e) for e in relevant]
            root = merkle_root(leaves)
            count = len(relevant)
            c = Commitment(sw.commitment.source_channel, sw.commitment.w,
                           sw.commitment.a, sw.commitment.b, root, count)
            endo = endorse(c, peer_keys, adversary_signers)
            out.append((c, endo))
        else:
            out.append((sw.commitment, sw.endorsement))
    return out


def attack_fabricate(windows, salt_key, peer_keys, adversary_signers):
    """Insert a fabricated event into a window."""
    out = []
    for idx, sw in enumerate(windows):
        if idx == 1:
            fake = Event("FABRICATED-TX", sw.commitment.b, 99,
                         sw.commitment.source_channel, b"forged", True)
            tampered = sw.events + [fake]
            root, count = window_root(salt_key, tampered)
            c = Commitment(sw.commitment.source_channel, sw.commitment.w,
                           sw.commitment.a, sw.commitment.b, root, count)
            endo = endorse(c, peer_keys, adversary_signers)
            out.append((c, endo))
        else:
            out.append((sw.commitment, sw.endorsement))
    return out


def attack_drop_interior_window(windows):
    """Skip an interior window (relay 1, 3, 4, ... omitting 2)."""
    out = []
    for idx, sw in enumerate(windows):
        if idx == 1:           # window w=2 (0-based index 1) is dropped
            continue
        out.append((sw.commitment, sw.endorsement))
    return out


def attack_replay(windows):
    """Re-submit an already-anchored window."""
    out = []
    for sw in windows:
        out.append((sw.commitment, sw.endorsement))
    if len(windows) >= 2:
        out.insert(2, (windows[1].commitment, windows[1].endorsement))  # replay w=2
    return out


def attack_drop_tail(windows, keep):
    """Stop relaying after `keep` windows (tail truncation)."""
    out = []
    for sw in windows[:keep]:
        out.append((sw.commitment, sw.endorsement))
    return out
