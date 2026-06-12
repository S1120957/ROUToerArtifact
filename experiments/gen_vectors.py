#!/usr/bin/env python3
"""Emit canonical conformance vectors from the Python reference.

The Node chaincode (chaincode/lib) must reproduce these byte-for-byte. If it
does not, the two implementations disagree and the Fabric deployment would
compute different Merkle roots than the reference simulator -- a correctness
bug. chaincode/test/conformance.test.js consumes vectors/conformance.json.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from oer.merkle import Event, leaf, merkle_root, window_root
from oer.commitment import Commitment, commitment_bytes

SALT_KEY = b"per-channel-salt-key-known-to-source-members-only"

events = [
    Event("tx-0-0", 0, 0, "domain-a-channel", b"payload-0-0", True),
    Event("tx-1-0", 1, 0, "domain-a-channel", b"payload-1-0", True),
    Event("tx-1-1", 1, 1, "domain-a-channel", b"ignore-me", False),  # not relevant
    Event("tx-2-0", 2, 0, "domain-a-channel", b"payload-2-0", True),
]

leaves = [{"eid": e.eid, "height": e.height, "tx_index": e.tx_index,
           "source_domain": e.source_domain,
           "payload_utf8": e.payload.decode(),
           "relevant": e.relevant,
           "leaf_hex": leaf(SALT_KEY, e).hex()} for e in events]

root, count = window_root(SALT_KEY, events)

cmt = Commitment("domain-a-channel", 1, 0, 2, root, count)
vectors = {
    "salt_key_utf8": SALT_KEY.decode(),
    "empty_root_hex": merkle_root([]).hex(),
    "events": leaves,
    "window_root_hex": root.hex(),
    "window_count": count,
    "commitment": {
        "source_channel": cmt.source_channel, "w": cmt.w, "a": cmt.a,
        "b": cmt.b, "root_hex": cmt.root.hex(), "count": cmt.count,
        "commitment_bytes_hex": commitment_bytes(cmt).hex(),
    },
}

out = os.path.join(os.path.dirname(__file__), "..", "vectors", "conformance.json")
with open(out, "w") as f:
    json.dump(vectors, f, indent=2)
print("wrote", out)
print("window_root:", root.hex())
