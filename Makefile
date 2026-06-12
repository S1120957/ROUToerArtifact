# Omission-Evident Reconciliation -- reproducible artifact.
# All targets run from a clean checkout. Security/conformance/storage need only
# Python 3.10+ and Node 18+; Fabric latency needs the testbed (network/README.md).

PY ?= python3
NODE ?= node

.PHONY: all security conformance test vectors storage local-bench tables \
        fabric-up fabric-deploy fabric-bench fabric-down clean help

help:
	@echo "Targets:"
	@echo "  make security      - run the deterministic omission-detection battery (REAL)"
	@echo "  make conformance   - check Node chaincode matches Python vectors byte-for-byte"
	@echo "  make test          - run the Python core unit tests"
	@echo "  make vectors       - regenerate cross-language conformance vectors"
	@echo "  make storage       - compute exact per-anchor world-state size (REAL)"
	@echo "  make local-bench   - local crypto complexity-trend bench (NOT Fabric)"
	@echo "  make tables        - regenerate paper/tab_security.tex + tab_cost.tex"
	@echo "  make all           - vectors + test + conformance + security + storage + tables"
	@echo "  --- Fabric testbed (requires FABRIC_SAMPLES; see network/README.md) ---"
	@echo "  make fabric-up / fabric-deploy / fabric-bench / fabric-down"
	@echo "  make clean         - remove generated artifacts and caches"

all: vectors test conformance security storage tables

# ---- deterministic, no Fabric required ----
vectors:
	$(PY) experiments/gen_vectors.py

test:
	$(PY) core/tests/test_protocol.py

conformance: vectors
	$(NODE) chaincode/test/conformance.test.js

security:
	$(PY) experiments/run_security_battery.py --json experiments/security_results.json

storage:
	$(NODE) bench/storage_size.js

local-bench:
	$(NODE) bench/local_crypto_bench.js

tables: security storage
	$(PY) experiments/gen_tables.py

# ---- Fabric testbed (cannot run without a real network) ----
fabric-up:
	bash network/scripts/network-up.sh

fabric-deploy:
	bash network/scripts/create-channels.sh
	bash network/scripts/deploy-chaincode.sh
	bash network/scripts/register-policies.sh

fabric-bench:
	$(NODE) bench/bench_fabric.js --iterations 100 --warmup 10
	$(PY) experiments/gen_tables.py

fabric-down:
	bash network/scripts/network-down.sh

clean:
	rm -rf core/oer/__pycache__ core/tests/__pycache__
	@echo "cleaned caches (generated result JSON and tables are kept under version control)"
