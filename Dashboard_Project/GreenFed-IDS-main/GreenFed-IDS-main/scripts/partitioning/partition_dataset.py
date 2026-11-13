
import json
from pathlib import Path

import numpy as np
import pandas as pd


# --------------------------------------------------
# Configuration
# --------------------------------------------------

NUM_CLIENTS = 5
DIRICHLET_ALPHA = 0.5
RANDOM_SEED = 42
LABEL_COLUMN = "Label"

# Project root: GreenFed-IDS-main/GreenFed-IDS-main
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Original dataset location: Minor_Project/output/splits
TRAIN_FILE = (
    PROJECT_ROOT.parent.parent
    / "output"
    / "splits"
    / "train.csv"
)

# New output location inside this project
OUTPUT_DIR = PROJECT_ROOT / "output" / "partitions"

IID_DIR = OUTPUT_DIR / "iid"
NON_IID_DIR = OUTPUT_DIR / "non_iid"

rng = np.random.default_rng(RANDOM_SEED)


# --------------------------------------------------
# Load only the Label column
# --------------------------------------------------

def load_labels():
    if not TRAIN_FILE.exists():
        raise FileNotFoundError(
            f"Training dataset not found: {TRAIN_FILE}"
        )

    labels = pd.read_csv(
        TRAIN_FILE,
        usecols=[LABEL_COLUMN]
    )[LABEL_COLUMN]

    if labels.isna().any():
        raise ValueError("Missing labels found in training data.")

    return labels.astype(str).to_numpy()


# --------------------------------------------------
# IID partitioning
# --------------------------------------------------

def create_iid_partitions(labels):
    client_indices = [[] for _ in range(NUM_CLIENTS)]

    # Split each class approximately equally among clients.
    # This preserves the overall class proportions.
    for class_name in np.unique(labels):
        class_indices = np.flatnonzero(labels == class_name)
        rng.shuffle(class_indices)

        splits = np.array_split(class_indices, NUM_CLIENTS)

        for client_id, split in enumerate(splits):
            client_indices[client_id].extend(split.tolist())

    return [
        np.sort(np.asarray(indices, dtype=np.int64))
        for indices in client_indices
    ]


# --------------------------------------------------
# Non-IID Dirichlet partitioning
# --------------------------------------------------

def create_non_iid_partitions(labels):
    client_indices = [[] for _ in range(NUM_CLIENTS)]

    for class_name in np.unique(labels):
        class_indices = np.flatnonzero(labels == class_name)
        rng.shuffle(class_indices)

        # Generate client proportions for this class.
        proportions = rng.dirichlet(
            np.repeat(DIRICHLET_ALPHA, NUM_CLIENTS)
        )

        # Convert proportions into exact record counts.
        counts = rng.multinomial(
            len(class_indices),
            proportions
        )

        start = 0

        for client_id, count in enumerate(counts):
            end = start + count

            assigned = class_indices[start:end]
            client_indices[client_id].extend(
                assigned.tolist()
            )

            start = end

    return [
        np.sort(np.asarray(indices, dtype=np.int64))
        for indices in client_indices
    ]


# --------------------------------------------------
# Validate and save partitions
# --------------------------------------------------

def save_and_validate(partitions, labels, output_dir, method):
    output_dir.mkdir(parents=True, exist_ok=True)

    all_indices = []
    client_reports = {}

    for client_id, indices in enumerate(partitions, start=1):
        # Save original train.csv row positions.
        np.save(
            output_dir / f"client_{client_id}_indices.npy",
            indices
        )

        all_indices.extend(indices.tolist())

        client_labels = labels[indices]
        unique_classes, counts = np.unique(
            client_labels,
            return_counts=True
        )

        class_distribution = {
            str(name): int(count)
            for name, count in zip(unique_classes, counts)
        }

        client_reports[f"client_{client_id}"] = {
            "records": int(len(indices)),
            "class_count": int(len(unique_classes)),
            "class_distribution": class_distribution
        }

    all_indices = np.asarray(all_indices, dtype=np.int64)

    # Every training row must appear exactly once.
    valid = (
        len(all_indices) == len(labels)
        and len(np.unique(all_indices)) == len(labels)
        and np.array_equal(
            np.sort(all_indices),
            np.arange(len(labels))
        )
    )

    if not valid:
        raise RuntimeError(
            f"{method} partition validation failed."
        )

    report = {
        "method": method,
        "number_of_clients": NUM_CLIENTS,
        "random_seed": RANDOM_SEED,
        "dirichlet_alpha": (
            DIRICHLET_ALPHA if method == "non_iid" else None
        ),
        "total_training_records": int(len(labels)),
        "records_assigned": int(len(all_indices)),
        "all_records_assigned_once": bool(valid),
        "clients": client_reports
    }

    with open(
        output_dir / "partition_report.json",
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(report, file, indent=4)

    return report


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():
    print("Loading CICIoT2023 training labels...")

    labels = load_labels()

    print(f"Training records: {len(labels):,}")
    print(f"Number of classes: {len(np.unique(labels))}")
    print(f"Number of clients: {NUM_CLIENTS}")

    print("\nCreating IID partitions...")
    iid_partitions = create_iid_partitions(labels)

    iid_report = save_and_validate(
        iid_partitions,
        labels,
        IID_DIR,
        "iid"
    )

    print("IID partitioning completed.")
    print(
        "IID records assigned:",
        f"{iid_report['records_assigned']:,}"
    )

    print("\nCreating Non-IID partitions...")
    non_iid_partitions = create_non_iid_partitions(labels)

    non_iid_report = save_and_validate(
        non_iid_partitions,
        labels,
        NON_IID_DIR,
        "non_iid"
    )

    print("Non-IID partitioning completed.")
    print(
        "Non-IID records assigned:",
        f"{non_iid_report['records_assigned']:,}"
    )

    print("\nAll partition validations passed.")
    print(f"Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
