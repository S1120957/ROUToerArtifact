#!/usr/bin/env bash
#
# collect_env.sh -- capture the exact testbed environment for the artifact
# appendix. Run this ON THE MACHINE where you run the Fabric latency benchmark
# (`make fabric-bench`), then paste the "LATEX BLOCK" output into the
# Implementation section in place of the environment \todonote.
#
# Rationale: the host/OS/Docker/Fabric versions are real, machine-specific facts
# that a reviewer needs to interpret the latency numbers. They must be measured,
# not guessed -- this script measures them so they are not mistyped.
#
# Usage: bash scripts/collect_env.sh
set -u

q() { "$@" 2>/dev/null || echo "N/A"; }

OS_PRETTY=$( (. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME") || echo "N/A")
KERNEL=$(q uname -sr)
if [ -n "${WSL_DISTRO_NAME:-}" ] || grep -qi microsoft /proc/version 2>/dev/null; then
  IS_WSL="yes (WSL2)"; WSL_TAG=", WSL2"
else
  IS_WSL="no"; WSL_TAG=""
fi
CPU_MODEL=$(awk -F: '/model name/{print $2; exit}' /proc/cpuinfo 2>/dev/null | sed 's/^ *//' || echo "N/A")
CPU_CORES=$(q nproc)
RAM=$(awk '/MemTotal/{printf "%.1f GiB", $2/1048576}' /proc/meminfo 2>/dev/null || echo "N/A")
DOCKER=$(q docker --version)
COMPOSE=$(q docker compose version)
FABRIC=$(q peer version | awk '/Version:/{print $2; exit}')
[ -z "$FABRIC" ] && FABRIC="N/A (peer not on PATH -- run after deploy)"
NODE=$(q node --version)
NPM=$(q npm --version)
PY=$(q python3 --version)
GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "N/A (not a git checkout)")

echo "============================ ENVIRONMENT ============================"
printf "%-18s %s\n" "OS:"            "$OS_PRETTY"
printf "%-18s %s\n" "Kernel:"        "$KERNEL"
printf "%-18s %s\n" "WSL2:"          "$IS_WSL"
printf "%-18s %s\n" "CPU:"           "$CPU_MODEL"
printf "%-18s %s\n" "Cores (logical):" "$CPU_CORES"
printf "%-18s %s\n" "RAM:"           "$RAM"
printf "%-18s %s\n" "Docker:"        "$DOCKER"
printf "%-18s %s\n" "Compose:"       "$COMPOSE"
printf "%-18s %s\n" "Fabric (peer):" "$FABRIC"
printf "%-18s %s\n" "Node.js:"       "$NODE"
printf "%-18s %s\n" "npm:"           "$NPM"
printf "%-18s %s\n" "Python:"        "$PY"
printf "%-18s %s\n" "Artifact commit:" "$GIT_COMMIT"

echo ""
echo "=========================== LATEX BLOCK ============================"
echo "% paste into the Implementation \\paragraph{Artifact and environment.}"
cat <<EOF
Measurements were taken on ${CPU_MODEL} (${CPU_CORES} logical cores, ${RAM}),
running ${OS_PRETTY} (${KERNEL}${WSL_TAG}), Docker ${DOCKER#Docker version },
Hyperledger Fabric ${FABRIC}, Node.js ${NODE}, and ${PY}.
EOF
echo "==================================================================="
