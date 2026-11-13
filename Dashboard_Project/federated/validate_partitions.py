"""Validate existing (or newly generated) client partitions.

Checks coverage, duplicates, index range, report consistency and test-set
isolation.  Read-only with respect to the dataset and existing reports.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from greenfed_fl.data import load_training_data
from greenfed_fl.partitioning import (
    class_share_std,
    load_partition_report,
    read_partition_indices,
    summarise_partition,
    validate_partition,
)
from greenfed_fl.paths import PARTITIONS_DIR, TRAIN_CSV


def validate_method(method: str, partitions_dir: Path, labels: np.ndarray) -> dict:
    directory = partitions_dir / method
    report = load_partition_report(directory)
    indices = read_partition_indices(directory)
    validation = validate_partition(indices, len(labels))

    recomputed = summarise_partition(indices, labels)
    report_mismatches = []
    for client, details in recomputed.items():
        reported = report["clients"].get(client)
        if reported is None:
            report_mismatches.append(f"{client}: missing from report")
            continue
        if reported["records"] != details["records"]:
            report_mismatches.append(
                f"{client}: records report={reported['records']} actual={details['records']}"
            )
        if reported["class_distribution"] != details["class_distribution"]:
            report_mismatches.append(f"{client}: class distribution mismatch")

    return {
        "directory": str(directory),
        "method": method,
        "reported_seed": report.get("random_seed"),
        "reported_alpha": report.get("dirichlet_alpha"),
        "reported_clients": report.get("number_of_clients"),
        "validation": validation,
        "class_share_std_percentage_points": round(class_share_std(report), 4),
        "report_matches_recomputed_indices": len(report_mismatches) == 0,
        "report_mismatches": report_mismatches,
        "max_index_less_than_train_rows": bool(
            all(len(part) == 0 or part.max() < len(labels) for part in indices)
        ),
        "test_rows_total": None,
        "test_set_used_for_partitioning": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-csv", type=Path, default=TRAIN_CSV)
    parser.add_argument("--partitions-dir", type=Path, default=PARTITIONS_DIR)
    parser.add_argument(
        "--methods", default="iid,non_iid", help="Comma-separated partition methods"
    )
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()

    labels = load_training_labels_only(args.train_csv)
    print(f"Training rows: {len(labels):,}")

    results = {}
    ok = True
    for method in [item.strip() for item in args.methods.split(",") if item.strip()]:
        result = validate_method(method, args.partitions_dir, labels)
        results[method] = result
        valid = (
            result["validation"]["all_records_assigned_once"]
            and result["validation"]["indices_in_valid_range"]
            and result["validation"]["duplicate_indices_across_clients"] == 0
            and result["report_matches_recomputed_indices"]
            and result["max_index_less_than_train_rows"]
        )
        ok = ok and valid
        print(
            f"\n[{method}] valid={valid} "
            f"records={result['validation']['records_assigned']:,} "
            f"duplicates={result['validation']['duplicate_indices_across_clients']} "
            f"class_share_std={result['class_share_std_percentage_points']}"
        )
        if not result["report_matches_recomputed_indices"]:
            for mismatch in result["report_mismatches"][:5]:
                print(f"  mismatch: {mismatch}")

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(results, indent=4), encoding="utf-8")
        print(f"\nWrote {args.json_out}")

    return 0 if ok else 1


def load_training_labels_only(csv_path: Path) -> np.ndarray:
    from greenfed_fl.partitioning import load_training_labels

    return load_training_labels(csv_path)


if __name__ == "__main__":
    sys.exit(main())
