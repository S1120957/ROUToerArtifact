"""Deterministic, length-prefixed canonical encoding.

This is the cross-language wire format. Both the Python reference simulator
and the Node chaincode MUST produce byte-identical encodings, otherwise the
Merkle roots will differ and conformance tests will fail. Keep this in lockstep
with chaincode/lib/encoding.js.

Design choice (correctness over elegance): we do NOT use JSON for anything that
is hashed. JSON number/whitespace/key-order handling differs subtly across
languages. Instead every field is encoded as an explicit, length-prefixed byte
string with a fixed field order.

Primitive encodings:
  enc_uint(n)  -> 8-byte big-endian unsigned integer
  enc_bytes(b) -> enc_uint(len(b)) || b
  enc_str(s)   -> enc_bytes(utf8(s))
"""
from __future__ import annotations
import hashlib


def enc_uint(n: int) -> bytes:
    if n < 0 or n >= (1 << 64):
        raise ValueError(f"uint out of range: {n}")
    return int(n).to_bytes(8, "big")


def enc_bytes(b: bytes) -> bytes:
    return enc_uint(len(b)) + b


def enc_str(s: str) -> bytes:
    return enc_bytes(s.encode("utf-8"))


def sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()
