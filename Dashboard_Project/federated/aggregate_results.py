"""Aggregate repeated experiment runs into mean/std tables.

Usage:
    python federated/aggregate_results.py --tag full
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np

from greenfed_fl.paths import RESULTS_DIR

METRICS = [
    "validation_accuracy",
    "validation_balanced_accuracy",
    "validation_macro_f1",
    "test_accuracy",
    "test_balanced_accuracy",
    "test_macro_f1",
    "test_weighted_f1",
    "communication_megabytes_total",
    "cpu_seconds_total",
    "training_seconds_total",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--tag", default="full")
    parser.add_argument("--out-prefix", default=None)
    args = parser.parse_args()

    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    seeds: dict[tuple[str, str], set[int]] = defaultdict(set)

    for summary_path in sorted(args.results_dir.glob("*/summary.json")):
        run_dir = summary_path.parent
        if args.tag and f"_{args.tag}" not in run_dir.name:
            continue
        metadata_path = run_dir / "run_metadata.json"
        if not metadata_path.is_file():
            continue
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        seed = int(metadata.get("train_config", {}).get("seed", -1))
        for row in json.loads(summary_path.read_text(encoding="utf-8")):
            key = (row["scenario"], row["strategy"])
            groups[key].append(row)
            seeds[key].add(seed)

    if not groups:
        print(f"No runs found under {args.results_dir} with tag '{args.tag}'")
        return 1

    aggregated = []
    for (scenario, strategy), rows in sorted(groups.items()):
        entry = {
            "scenario": scenario,
            "strategy": strategy,
            "seeds": sorted(seeds[(scenario, strategy)]),
            "num_runs": len(rows),
        }
        for metric in METRICS:
            values = np.array(
                [row[metric] for row in rows if row.get(metric) is not None],
                dtype=float,
            )
            entry[f"{metric}_mean"] = float(values.mean()) if len(values) else None
            entry[f"{metric}_std"] = (
                float(values.std(ddof=1)) if len(values) > 1 else 0.0
            )
        aggregated.append(entry)

    prefix = args.out_prefix or f"aggregate_{args.tag}"
    json_path = args.results_dir / f"{prefix}.json"
    csv_path = args.results_dir / f"{prefix}.csv"
    md_path = args.results_dir / f"{prefix}.md"

    json_path.write_text(json.dumps(aggregated, indent=4), encoding="utf-8")

    fieldnames = ["scenario", "strategy", "num_runs", "seeds"]
    for metric in METRICS:
        fieldnames.extend([f"{metric}_mean", f"{metric}_std"])
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in aggregated:
            serialised = dict(row)
            serialised["seeds"] = "|".join(str(seed) for seed in row["seeds"])
            writer.writerow(serialised)

    lines = [
        f"# Aggregated experiments ({args.tag})",
        "",
        "Mean and sample std over independent random seeds. Held-out test set is never used for training or selection.",
        "",
        "| Scenario | Strategy | Runs | Test accuracy | Test macro-F1 | Comm. MB | CPU s |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in aggregated:
        lines.append(
            "| {scenario} | {strategy} | {num_runs} | {acc:.4f} and {acc_s:.4f} | "
            "{f1:.4f} and {f1_s:.4f} | {comm:.3f} and {comm_s:.3f} | "
            "{cpu:.2f} and {cpu_s:.2f} |".format(
                scenario=row["scenario"],
                strategy=row["strategy"],
                num_runs=row["num_runs"],
                acc=row["test_accuracy_mean"],
                acc_s=row["test_accuracy_std"],
                f1=row["test_macro_f1_mean"],
                f1_s=row["test_macro_f1_std"],
                comm=row["communication_megabytes_total_mean"],
                comm_s=row["communication_megabytes_total_std"],
                cpu=row["cpu_seconds_total_mean"],
                cpu_s=row["cpu_seconds_total_std"],
            )
        )

    lines.extend(
        [
            "",
            "## Efficiency relative to full-participation FedAvg",
            "",
            "| Scenario | Strategy | Delta accuracy (pp) | Comm. reduction | CPU reduction |",
            "|---|---|---:|---:|---:|",
        ]
    )
    baseline = {
        row["scenario"]: row
        for row in aggregated
        if row["strategy"] == "all"
    }
    for row in aggregated:
        base = baseline.get(row["scenario"])
        if not base:
            continue
        acc_delta = (
            row["test_accuracy_mean"] - base["test_accuracy_mean"]
        ) * 100
        comm_reduction = (
            1
            - row["communication_megabytes_total_mean"]
            / base["communication_megabytes_total_mean"]
        ) * 100
        cpu_reduction = (
            1 - row["cpu_seconds_total_mean"] / base["cpu_seconds_total_mean"]
        ) * 100
        lines.append(
            f"| {row['scenario']} | {row['strategy']} | {acc_delta:+.2f} | "
            f"{comm_reduction:.1f}% | {cpu_reduction:.1f}% |"
        )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n".join(lines))
    print(f"\nWrote {json_path}\nWrote {csv_path}\nWrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


