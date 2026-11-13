"""Generate a client-context file from a real partition report.

Resource/network values are simulated by default and clearly labelled.
Local sample counts and class coverage are computed from real partitions.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from greenfed_fl.context import generate_simulated_context, write_context_file
from greenfed_fl.partitioning import load_partition_report
from greenfed_fl.paths import CONTEXT_DIR, PARTITIONS_DIR


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--method", default="iid", choices=["iid", "non_iid"])
    parser.add_argument("--partitions-dir", type=Path, default=PARTITIONS_DIR)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-jitter", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    report = load_partition_report(args.partitions_dir / args.method)
    clients, metadata = generate_simulated_context(
        report, seed=args.seed, jitter=not args.no_jitter
    )

    output = args.out or (
        CONTEXT_DIR / f"{args.method}_context_seed{args.seed}.json"
    )
    write_context_file(output, clients, metadata)

    print(f"Wrote simulated context for {len(clients)} clients: {output}")
    print("Fields labelled 'simulated' are not physical measurements.")
    if args.out is None:
        print(json.dumps(metadata, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
