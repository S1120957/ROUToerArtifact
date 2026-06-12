#!/usr/bin/env python3
"""_aggregate.py -- turn raw latency samples into bench_results.json.

Reads one file per operation (one millisecond sample per line) and writes the
median/p95 in exactly the schema experiments/gen_tables.py expects, so that
`make tables` then fills the Fabric latency rows of Table 2.

Usage:
  python3 _aggregate.py OUT.json WARMUP LABEL1 FILE1 [LABEL2 FILE2 ...]
Labels and file paths are ALTERNATING args (labels may contain '=', e.g.
"CommitWindow N=100"). The first WARMUP samples of each file are discarded.
"""
import json
import sys
import statistics


def pctl(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    return xs[min(len(xs) - 1, int(p * len(xs)))]


def main():
    out = sys.argv[1]
    warmup = int(sys.argv[2])
    rest = sys.argv[3:]
    if len(rest) % 2 != 0:
        sys.exit("expected alternating LABEL FILE arguments")
    ops = {}
    for i in range(0, len(rest), 2):
        label, path = rest[i], rest[i + 1]
        with open(path) as f:
            xs = [float(x) for x in f.read().split() if x.strip()]
        xs = xs[warmup:]
        if xs:
            ops[label] = {"median_ms": round(statistics.median(xs), 2),
                          "p95_ms": round(pctl(xs, 0.95), 2), "n": len(xs)}
        else:
            ops[label] = {"median_ms": "TO_BE_MEASURED",
                          "p95_ms": "TO_BE_MEASURED", "n": 0}
    result = {"environment": "see scripts/collect_env.sh output",
              "warmup": warmup, "operations": ops}
    with open(out, "w") as f:
        json.dump(result, f, indent=2)
    print("wrote", out)
    for k, v in ops.items():
        print(f"  {k}: median={v['median_ms']} ms  p95={v['p95_ms']} ms  (n={v['n']})")


if __name__ == "__main__":
    main()
