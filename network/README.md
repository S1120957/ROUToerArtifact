# Fabric network (single-host, TRL-4 testbed)

This deploys the protocol on a **single host** using the Hyperledger Fabric
`test-network` from `fabric-samples`. It is the testbed for the *Fabric-timing*
measurements only; the security results do not require it (see top-level
`README.md`, `make security`).

## Prerequisites (pin these versions in your paper's artifact appendix)

- Docker + Docker Compose
- Hyperledger Fabric 2.5 binaries and Docker images, and `fabric-samples` 2.5
  (`curl -sSL https://bit.ly/2ysbOFE | bash -s -- 2.5.9 1.5.7`)
- Node.js >= 18

Record the exact versions you used (CPU, RAM, OS kernel, Docker, Fabric, Node)
in the artifact appendix — reviewers need them to interpret the latency numbers.

## Channels

| Channel              | Role                | Chaincode             |
|----------------------|---------------------|-----------------------|
| `domain-a-channel`   | source domain A     | `commitWindow`        |
| `domain-b-channel`   | source domain B     | `commitWindow`        |
| `domain-c-channel`   | source domain C     | `commitWindow`        |
| `coordination-channel` | coordination      | `anchor`              |

Source channels use a per-channel endorsement policy `P_s` (e.g. 2-of-3). The
coordination channel uses a MAJORITY policy. Set these in `configtx.yaml`.

## Steps (from a clean checkout)

```bash
export FABRIC_SAMPLES=/path/to/fabric-samples     # required
cd network
./scripts/network-up.sh        # starts orderer + peers (test-network)
./scripts/create-channels.sh   # creates the 4 channels above
./scripts/deploy-chaincode.sh  # packages + installs commitWindow and anchor
# register each source policy on the coordination channel:
./scripts/register-policies.sh
```

Tear down with `./scripts/network-down.sh`.

## After the network is up

Run the Fabric latency harness from the repo root (it fills Table 2):

```bash
export FABRIC_GATEWAY_ENDPOINT=localhost:7051     # your peer gateway
# ... set the remaining identity/TLS env vars your gateway needs ...
node bench/bench_fabric.js --iterations 100 --warmup 10
python3 experiments/gen_tables.py                  # regenerates paper/tab_cost.tex
```

Until `bench_fabric.js` runs against a live gateway, `paper/tab_cost.tex` shows
`TO_BE_MEASURED` for the Fabric latency rows (by design — no invented numbers).
