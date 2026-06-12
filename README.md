# Omission-Evident Cross-Domain Reconciliation (OER)

Reference artifact for the paper on auditable completeness under channel
confidentiality: detecting omission of a derived cross-domain record by a
verifier that has **no source-channel read access** and trusts **no
coordinator** (Byzantine coordinator). Permissioned Hyperledger Fabric.

The artifact is deliberately split into two layers so that the security claims
do not depend on timing or hardware:

| Layer | What it is | What it produces | Needs Fabric? |
|-------|-----------|------------------|---------------|
| `core/` (Python) | stdlib-only reference simulator + adversary | the **real** omission-detection results (Table 1) | no |
| `chaincode/` (Node) | Fabric 2.5 chaincode + conformance test | byte-identical roots to the reference; deployable contracts | no for conformance; yes for latency |

> **Honesty policy.** Deterministic results (omission detection, per-anchor
> storage size, cross-language conformance) are run for real and committed.
> Hardware/Fabric-bound results (per-operation latency, throughput) are
> **`TO_BE_MEASURED`** with runnable harnesses and step-by-step instructions.
> No experimental numbers are invented.

## Quick start (clean checkout, no Fabric needed)

Requirements: Python >= 3.10, Node >= 18. No third-party Python packages.

```bash
make all
```

This runs, in order: regenerate conformance vectors -> Python unit tests ->
Node/Python cross-language conformance -> the adversarial security battery ->
per-anchor storage size -> regenerate the paper tables. Expected tail of output:

```
RESULT: ALL EXPECTATIONS MET          # security battery: all 6 attacks detected
conformance: 8 checks PASSED          # Node matches Python byte-for-byte
7/7 passed                            # core unit tests
wrote paper/tab_security.tex
wrote paper/tab_cost.tex
```

Individual targets: `make security`, `make conformance`, `make test`,
`make storage`, `make tables`, `make local-bench` (see `make help`).

## What each experiment shows

- **`make security`** — a Byzantine coordinator (controlling a sub-quorum of
  source peers) attempts six omission behaviours: drop-within-window,
  drop-interior-window, tail-truncation, reorder, fabricate, replay. Each is
  detected, either rejected at commit by the `Anchor` predicate or flagged by
  the off-chain verifier's freshness deadline. The honest baseline is accepted.
  Outcomes are deterministic and reproducible on any machine.
- **`make conformance`** — proves the Node chaincode's Merkle/commitment logic
  reproduces the Python reference vectors exactly (same roots, leaves, and
  signing pre-images). This is what lets the deterministic security results
  stand in for the deployed chaincode's behaviour.
- **`make storage`** — exact serialized world-state size per anchor (real;
  $O(1)$ in events-per-window because only the root is stored).

## Fabric latency (the `TO_BE_MEASURED` part)

The per-operation latency rows of the cost table require a real network. See
[`network/README.md`](network/README.md) for the single-host testbed
(`fabric-samples` 2.5). Summary:

```bash
export FABRIC_SAMPLES=/path/to/fabric-samples
make fabric-up && make fabric-deploy
export FABRIC_GATEWAY_ENDPOINT=localhost:7051   # + your identity/TLS env
make fabric-bench        # fills bench/bench_results.json, regenerates tab_cost.tex
make fabric-down
```

Record the exact host, OS, Docker, Fabric, and Node versions in your artifact
appendix so reviewers can interpret the latency numbers.

## Layout

```
core/        Python reference simulator (encoding, merkle, commitment,
             anchor predicate, verifier) + adversary + unit tests
chaincode/   Fabric Node chaincode: source/CommitWindow, coordination/Anchor,
             shared lib/, and the cross-language conformance test
network/     single-host Fabric testbed scripts + README
bench/       storage size (real), Fabric latency harness (TO_BE_MEASURED),
             local crypto trend (NOT Fabric)
experiments/ security battery, vector generator, table generator
paper/       implementation.tex, evaluation.tex, auto-generated tables
vectors/     cross-language conformance vectors
```

## Mapping to the paper

- Table 1 (adversarial detection) <- `experiments/security_results.json` via `make tables`
- Table 2 (cost): storage row real; Fabric latency rows `TO_BE_MEASURED`
- `paper/implementation.tex`, `paper/evaluation.tex` replace the draft's TODO sections

## License

Apache-2.0 (see `LICENSE`).
