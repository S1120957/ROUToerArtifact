#!/usr/bin/env python3
"""Unit tests for the OER reference core. Run: python3 core/tests/test_protocol.py
Uses plain asserts so there is no third-party test dependency."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from oer import (Event, window_root, merkle_root, leaf, Commitment,
                 EndorsementPolicy, endorse, endorsement_valid,
                 AnchorContract, AnchorReject, verify)

SALT = b"k_s"
PK = {"p0": b"a", "p1": b"b", "p2": b"c"}
POL = EndorsementPolicy(("p0", "p1", "p2"), 2)


def ev(eid, h, ti, rel=True):
    return Event(eid, h, ti, "src", f"pl-{eid}".encode(), rel)


def test_canonical_order_independence():
    a = [ev("x", 1, 0), ev("y", 0, 0), ev("z", 0, 1)]
    b = list(reversed(a))
    assert window_root(SALT, a) == window_root(SALT, b), "root must be order-independent under canonicalisation"


def test_relevance_filter():
    a = [ev("x", 0, 0, True), ev("y", 1, 0, False)]
    root, count = window_root(SALT, a)
    assert count == 1, "irrelevant events must be excluded"


def test_empty_root_stable():
    assert merkle_root([]) == merkle_root([]), "empty root deterministic"


def test_tamper_changes_root():
    a = [ev("x", 0, 0), ev("y", 1, 0)]
    r1, _ = window_root(SALT, a)
    b = [ev("x", 0, 0), ev("y", 1, 0, True)]
    b[1] = Event("y", 1, 0, "src", b"DIFFERENT", True)
    r2, _ = window_root(SALT, b)
    assert r1 != r2, "payload change must change root"


def test_endorsement_quorum():
    c = Commitment("src", 1, 0, 1, b"\x00" * 32, 0)
    one = endorse(c, PK, ["p0"])
    two = endorse(c, PK, ["p0", "p1"])
    assert not endorsement_valid(c, one, POL, PK), "sub-quorum must fail"
    assert endorsement_valid(c, two, POL, PK), "quorum must pass"


def test_anchor_monotonic_contiguous():
    ac = AnchorContract({"src": POL}, {"src": PK})
    c1 = Commitment("src", 1, 0, 1, b"\x01" * 32, 1)
    ac.anchor(c1, endorse(c1, PK, ["p0", "p1"]), 1)
    # skipping window 2 must be rejected
    c3 = Commitment("src", 3, 4, 5, b"\x03" * 32, 1)
    try:
        ac.anchor(c3, endorse(c3, PK, ["p0", "p1"]), 2)
        assert False, "interior gap must be rejected"
    except AnchorReject as e:
        assert e.reason == "non-monotonic-window"


def test_verify_accepts_honest():
    ac = AnchorContract({"src": POL}, {"src": PK})
    h = 0
    for w in range(1, 4):
        a, b = (w - 1) * 2, (w - 1) * 2 + 1
        c = Commitment("src", w, a, b, bytes([w]) * 32, 1)
        h += 1
        ac.anchor(c, endorse(c, PK, ["p0", "p1"]), h)
    res = verify(ac.log, {"src": POL}, {"src": PK}, delta=2, coord_frontier_height=3)
    assert res.accepted, f"honest log must verify, got {res.reason}"


def main():
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
