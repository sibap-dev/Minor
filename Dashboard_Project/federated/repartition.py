"""Generate new client partitions into a separate directory.

Existing artifacts under ``output/partitions`` are never modified unless the
caller explicitly points at them with ``--overwrite``; the previous report is
archived in that case.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from greenfed_fl.data import feature_columns_from_header, load_test_data
from greenfed_fl.partitioning import (
    PartitionConfig,
    class_share_std,
    create_partition,
    load_training_labels,
    write_partition,
)
from greenfed_fl.paths import PARTITIONS_DIR, TRAIN_CSV


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-csv", type=Path, default=TRAIN_CSV)
    parser.add_argument("--method", default="non_iid", choices=["iid", "non_iid"])
    parser.add_argument("--num-clients", type=int, default=5)
    parser.add_argument("--alpha", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Defaults to <partitions-dir>/<method>_c<N>_a<alpha>_s<seed>",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    config = PartitionConfig(
        num_clients=args.num_clients,
        method=args.method,
        alpha=args.alpha if args.method == "non_iid" else None,
        seed=args.seed,
    )

    labels = load_training_labels(args.train_csv)
    print(f"Training rows: {len(labels):,}")
    partitions = create_partition(labels, config)

    output = args.output_dir or (
        PARTITIONS_DIR
        / f"{args.method}_c{args.num_clients}_a{args.alpha:g}_s{args.seed}"
    )

    report = write_partition(
        partitions,
        labels,
        output,
        config,
        metadata={
            "train_csv": str(args.train_csv),
            "generator": "federated/repartition.py",
            "test_set_used_for_partitioning": False,
        },
        overwrite=args.overwrite,
    )

    print(f"Wrote partitions to {output}")
    print(f"Validation: {report['all_records_assigned_once']}")
    print(f"Class-share std (pp): {class_share_std(report):.4f}")
    for client, details in report["clients"].items():
        print(
            f"  {client}: {details['records']:,} records "
            f"({details['percentage']:.2f}%), {details['class_count']} classes"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
