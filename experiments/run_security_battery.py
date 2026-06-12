#!/usr/bin/env python3
"""Run the adversarial omission-detection battery and emit real results.

This is a DETERMINISTIC security experiment, not a performance benchmark. Its
outputs (which attacks are detected, and by which mechanism) are real, exact,
and reproducible from a clean checkout on any machine with Python 3.10+ --
they do not depend on Fabric or hardware. The results populate Table 1 of the
paper via experiments/gen_tables.py.

Usage:
    python3 experiments/run_security_battery.py            # human-readable
    python3 experiments/run_security_battery.py --json out.json
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from oer import Event, EndorsementPolicy, AnchorContract, AnchorReject, verify
from oer.adversary import (
    build_honest_windows, relay_honest,
    attack_drop_within_window, attack_reorder_within_window, attack_fabricate,
    attack_drop_interior_window, attack_replay, attack_drop_tail,
)

# --- fixed experimental scenario -------------------------------------------
SOURCE = "domain-a-channel"
SALT_KEY = b"per-channel-salt-key-known-to-source-members-only"
# three source peers, 2-of-3 endorsement policy.
# PEER_KEYS_FLAT is the per-channel {peer: key} map used when signing/endorsing
# a single source channel; PEER_KEYS is the {source: {peer: key}} map the
# AnchorContract and verifier use across all channels.
PEER_KEYS_FLAT = {"peer0": b"k0", "peer1": b"k1", "peer2": b"k2"}
PEER_KEYS = {SOURCE: PEER_KEYS_FLAT}
POLICY = {SOURCE: EndorsementPolicy(members=("peer0", "peer1", "peer2"), quorum=2)}
HONEST_SIGNERS = ["peer0", "peer1"]      # honest quorum
ADVERSARY_SIGNERS = ["peer2"]            # adversary controls 1 of 3 -> sub-quorum
DELTA = 3                                 # freshness deadline (coord blocks)
NUM_WINDOWS = 8                           # source produces 8 windows (heights 0..15)


def make_windows():
    """Five contiguous windows of relevant events, heights 0..9."""
    specs = []
    for w in range(NUM_WINDOWS):
        a, b = w * 2, w * 2 + 1
        evs = [
            Event(f"tx-{a}-0", a, 0, SOURCE, f"payload-{a}-0".encode(), True),
            Event(f"tx-{b}-0", b, 0, SOURCE, f"payload-{b}-0".encode(), True),
        ]
        specs.append((a, b, evs))
    return build_honest_windows(SOURCE, SALT_KEY, specs, PEER_KEYS_FLAT, HONEST_SIGNERS)


def run_stream(stream, coord_frontier):
    """Feed an attacker's (commitment, endorsement) stream into a fresh anchor
    contract, then run the verifier. Returns (detected, caught_by, reason)."""
    ac = AnchorContract(POLICY, PEER_KEYS)
    coord_h = 0
    for c, endo in stream:
        coord_h += 1
        try:
            ac.anchor(c, endo, coord_h)
        except AnchorReject as r:
            return True, "anchor", r.reason          # rejected at commit time
    res = verify(ac.log, POLICY, PEER_KEYS, DELTA, coord_frontier)
    if not res.accepted:
        return True, "verify", res.reason            # flagged by verifier
    return False, "none", "accepted"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    W = make_windows()
    cases = []

    # sanity: honest coordinator must be ACCEPTED (guards against a trivially
    # reject-everything implementation).
    detected, by, reason = run_stream(list(relay_honest(W)), coord_frontier=len(W))
    cases.append({"behaviour": "honest baseline", "expect_detected": False,
                  "detected": detected, "caught_by": by, "reason": reason,
                  "maps_to": "completeness (Def. 3)"})

    # the six adversarial behaviours
    detected, by, reason = run_stream(
        attack_drop_within_window(W, SALT_KEY, PEER_KEYS_FLAT, ADVERSARY_SIGNERS),
        coord_frontier=len(W))
    cases.append({"behaviour": "drop event within a window", "expect_detected": True,
                  "detected": detected, "caught_by": by, "reason": reason,
                  "maps_to": "Thm. 1 (root mismatch)"})

    detected, by, reason = run_stream(attack_drop_interior_window(W),
                                      coord_frontier=len(W))
    cases.append({"behaviour": "drop an interior window", "expect_detected": True,
                  "detected": detected, "caught_by": by, "reason": reason,
                  "maps_to": "Thm. 2 (commit-time reject)"})

    detected, by, reason = run_stream(attack_drop_tail(W, keep=3),
                                      coord_frontier=len(W))
    cases.append({"behaviour": "drop the tail (truncation)", "expect_detected": True,
                  "detected": detected, "caught_by": by, "reason": reason,
                  "maps_to": "freshness deadline (stall)"})

    detected, by, reason = run_stream(
        attack_reorder_within_window(W, SALT_KEY, PEER_KEYS_FLAT, ADVERSARY_SIGNERS),
        coord_frontier=len(W))
    cases.append({"behaviour": "reorder within a window", "expect_detected": True,
                  "detected": detected, "caught_by": by, "reason": reason,
                  "maps_to": "Thm. 3"})

    detected, by, reason = run_stream(
        attack_fabricate(W, SALT_KEY, PEER_KEYS_FLAT, ADVERSARY_SIGNERS),
        coord_frontier=len(W))
    cases.append({"behaviour": "insert a fabricated event", "expect_detected": True,
                  "detected": detected, "caught_by": by, "reason": reason,
                  "maps_to": "Thm. 3"})

    detected, by, reason = run_stream(attack_replay(W), coord_frontier=len(W))
    cases.append({"behaviour": "replay an old window", "expect_detected": True,
                  "detected": detected, "caught_by": by, "reason": reason,
                  "maps_to": "Thm. 4"})

    # report + assert
    ok = True
    width = max(len(c["behaviour"]) for c in cases)
    print(f"{'behaviour':<{width}}  detected  caught_by  reason")
    print("-" * (width + 38))
    for c in cases:
        status = "OK" if c["detected"] == c["expect_detected"] else "FAIL"
        if status == "FAIL":
            ok = False
        print(f"{c['behaviour']:<{width}}  "
              f"{str(c['detected']):<8}  {c['caught_by']:<9}  {c['reason']}")
    print("-" * (width + 38))
    print("RESULT:", "ALL EXPECTATIONS MET" if ok else "FAILURE")

    if args.json:
        with open(args.json, "w") as f:
            json.dump({"scenario": {"policy": "2-of-3", "windows": len(W),
                                    "delta": DELTA},
                       "cases": cases, "all_ok": ok}, f, indent=2)
        print("wrote", args.json)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
