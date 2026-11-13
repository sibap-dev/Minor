"""Reusable, deterministic client partitioning for CICIoT2023.

This module does not modify the existing partitions.  It can be used to
validate them or to generate new partitions into a separate output directory.
Only the training split is ever read.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from .paths import LABEL_COLUMN, require_file


@dataclass(frozen=True)
class PartitionConfig:
    num_clients: int = 5
    method: str = "iid"  # "iid" | "non_iid"
    alpha: float | None = 0.5
    seed: int = 42

    def __post_init__(self) -> None:
        if self.num_clients < 1:
            raise ValueError("num_clients must be >= 1")
        if self.method not in {"iid", "non_iid"}:
            raise ValueError("method must be 'iid' or 'non_iid'")
        if self.method == "non_iid":
            if self.alpha is None or not (0.0 < float(self.alpha)):
                raise ValueError("non_iid partitioning requires alpha > 0")


def load_training_labels(csv_path: str | Path) -> np.ndarray:
    """Load only the label column from the training split."""

    path = require_file(Path(csv_path), "Training CSV")
    labels = pd.read_csv(path, usecols=[LABEL_COLUMN])[LABEL_COLUMN]
    if labels.isna().any():
        raise ValueError("Missing labels found in training data")
    return labels.astype(str).str.strip().to_numpy()


def create_iid_partition(
    labels: np.ndarray, config: PartitionConfig
) -> list[np.ndarray]:
    """Class-proportional IID allocation: split every class evenly."""

    rng = np.random.default_rng(config.seed)
    client_indices: list[list[int]] = [[] for _ in range(config.num_clients)]

    for class_name in np.unique(labels):
        class_indices = np.flatnonzero(labels == class_name)
        rng.shuffle(class_indices)
        for client_id, split in enumerate(
            np.array_split(class_indices, config.num_clients)
        ):
            client_indices[client_id].extend(split.tolist())

    return [
        np.sort(np.asarray(indices, dtype=np.int64))
        for indices in client_indices
    ]


def create_dirichlet_partition(
    labels: np.ndarray, config: PartitionConfig
) -> list[np.ndarray]:
    """Class-wise Dirichlet allocation (one Dirichlet draw per class)."""

    rng = np.random.default_rng(config.seed)
    alpha = float(config.alpha)  # validated by config
    client_indices: list[list[int]] = [[] for _ in range(config.num_clients)]

    for class_name in np.unique(labels):
        class_indices = np.flatnonzero(labels == class_name)
        rng.shuffle(class_indices)

        proportions = rng.dirichlet(np.repeat(alpha, config.num_clients))
        counts = rng.multinomial(len(class_indices), proportions)

        start = 0
        for client_id, count in enumerate(counts):
            end = start + int(count)
            client_indices[client_id].extend(class_indices[start:end].tolist())
            start = end

    return [
        np.sort(np.asarray(indices, dtype=np.int64))
        for indices in client_indices
    ]


def create_partition(labels: np.ndarray, config: PartitionConfig) -> list[np.ndarray]:
    if config.method == "iid":
        return create_iid_partition(labels, config)
    return create_dirichlet_partition(labels, config)


def validate_partition(
    partitions: Sequence[np.ndarray], total_training_records: int
) -> dict:
    """Return a validation dictionary; raises only on structurally invalid input."""

    if len(partitions) == 0:
        raise ValueError("No partitions supplied")

    all_indices = np.concatenate(
        [np.asarray(p, dtype=np.int64) for p in partitions]
    ) if any(len(p) for p in partitions) else np.array([], dtype=np.int64)

    per_client_duplicates = {}
    for i, part in enumerate(partitions, start=1):
        if len(np.unique(part)) != len(part):
            per_client_duplicates[f"client_{i}"] = int(len(part) - len(np.unique(part)))

    in_range = bool(
        all_indices.size > 0
        and all_indices.min() >= 0
        and all_indices.max() < total_training_records
    )
    exact_cover = bool(
        all_indices.size == total_training_records
        and np.unique(all_indices).size == total_training_records
        and np.array_equal(np.sort(all_indices), np.arange(total_training_records))
    )

    return {
        "total_training_records": int(total_training_records),
        "records_assigned": int(all_indices.size),
        "unique_indices": int(np.unique(all_indices).size),
        "duplicate_indices_across_clients": int(
            all_indices.size - np.unique(all_indices).size
        ),
        "per_client_duplicates": per_client_duplicates,
        "indices_in_valid_range": in_range,
        "all_records_assigned_once": exact_cover,
        "empty_clients": [
            i for i, part in enumerate(partitions, start=1) if len(part) == 0
        ],
        "test_split_used": False,
    }


def class_distribution(labels: np.ndarray, indices: np.ndarray) -> dict[str, int]:
    values, counts = np.unique(labels[indices], return_counts=True)
    return {str(value): int(count) for value, count in zip(values, counts)}


def summarise_partition(
    partitions: Sequence[np.ndarray], labels: np.ndarray
) -> dict:
    total = int(len(labels))
    clients = {}
    for client_id, indices in enumerate(partitions, start=1):
        distribution = class_distribution(labels, indices)
        clients[f"client_{client_id}"] = {
            "records": int(len(indices)),
            "percentage": round(len(indices) / total * 100, 4) if total else 0.0,
            "class_count": len(distribution),
            "class_distribution": distribution,
        }
    return clients


def write_partition(
    partitions: Sequence[np.ndarray],
    labels: np.ndarray,
    output_dir: str | Path,
    config: PartitionConfig,
    metadata: dict | None = None,
    overwrite: bool = False,
) -> dict:
    """Write indices and a self-describing report.  Existing files are kept
    unless overwrite=True, and any overwrite is accompanied by a copy of the
    previous report in ``archive/``.
    """

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    validation = validate_partition(partitions, len(labels))
    if not validation["all_records_assigned_once"]:
        raise RuntimeError(
            f"Partition validation failed for {config.method}: {validation}"
        )

    report_path = output_dir / "partition_report.json"
    if report_path.exists() and overwrite:
        archive = output_dir / "archive"
        archive.mkdir(exist_ok=True)
        existing = json.loads(report_path.read_text(encoding="utf-8"))
        archive_name = (
            f"partition_report_{existing.get('random_seed', 'unknown')}_"
            f"{existing.get('dirichlet_alpha', 'iid')}.json"
        )
        (archive / archive_name).write_text(
            json.dumps(existing, indent=4), encoding="utf-8"
        )
    elif report_path.exists() and not overwrite:
        raise FileExistsError(
            f"{report_path} exists. Use overwrite=True or a new output directory."
        )

    for client_id, indices in enumerate(partitions, start=1):
        np.save(output_dir / f"client_{client_id}_indices.npy", indices)

    report = {
        "method": config.method,
        "number_of_clients": config.num_clients,
        "random_seed": config.seed,
        "dirichlet_alpha": config.alpha if config.method == "non_iid" else None,
        "total_training_records": int(len(labels)),
        "records_assigned": validation["records_assigned"],
        "all_records_assigned_once": validation["all_records_assigned_once"],
        "test_set_used_for_partitioning": False,
        "validation": validation,
        "clients": summarise_partition(partitions, labels),
        "metadata": metadata or {},
    }

    report_path.write_text(json.dumps(report, indent=4), encoding="utf-8")
    return report


def read_partition_indices(directory: str | Path) -> list[np.ndarray]:
    directory = Path(directory)
    files = sorted(directory.glob("client_*_indices.npy"))
    if not files:
        raise FileNotFoundError(f"No client index files found in {directory}")
    return [np.load(path) for path in files]


def load_partition_report(directory: str | Path) -> dict:
    path = Path(directory) / "partition_report.json"
    if not path.is_file():
        raise FileNotFoundError(f"Partition report not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def class_share_std(report: dict) -> float:
    """Mean per-class standard deviation of client allocation percentages.

    This is the same descriptive statistic reported for the original
    partitions: for every class, compute the percentage of that class assigned
    to each client, take the standard deviation, then average over classes.
    """

    clients = list(report["clients"].values())
    classes = sorted(
        {label for client in clients for label in client["class_distribution"]}
    )
    class_stds = []
    for label in classes:
        counts = np.array(
            [client["class_distribution"].get(label, 0) for client in clients],
            dtype=float,
        )
        total = counts.sum()
        if total <= 0:
            continue
        percentages = counts / total * 100.0
        # Sample standard deviation (ddof=1) matches the previously reported
        # "average class-wise percentage standard deviation" metric.
        class_stds.append(float(percentages.std(ddof=1)))
    return float(np.mean(class_stds)) if class_stds else 0.0


def compare_reports(iid_report: dict, non_iid_report: dict) -> dict:
    return {
        "iid": {
            "validation": iid_report["all_records_assigned_once"],
            "class_share_std_percentage_points": round(
                class_share_std(iid_report), 4
            ),
            "clients": {
                name: {
                    "records": details["records"],
                    "percentage": details["percentage"],
                    "classes": details["class_count"],
                }
                for name, details in iid_report["clients"].items()
            },
        },
        "non_iid": {
            "validation": non_iid_report["all_records_assigned_once"],
            "dirichlet_alpha": non_iid_report.get("dirichlet_alpha"),
            "class_share_std_percentage_points": round(
                class_share_std(non_iid_report), 4
            ),
            "clients": {
                name: {
                    "records": details["records"],
                    "percentage": details["percentage"],
                    "classes": details["class_count"],
                }
                for name, details in non_iid_report["clients"].items()
            },
        },
    }
