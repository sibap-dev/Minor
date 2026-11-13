
import json
from pathlib import Path
from collections import Counter

import pandas as pd

DATA_DIR = Path(r"D:\vs code\Minor_Project\output\splits")
CHUNK_SIZE = 100_000

FILES = {
    "train": DATA_DIR / "train.csv",
    "test": DATA_DIR / "test.csv",
}


def inspect_csv(name, file_path):
    if not file_path.exists():
        raise FileNotFoundError(f"Missing dataset: {file_path}")

    print(f"\nInspecting {name}: {file_path}")

    total_rows = 0
    label_counts = Counter()
    missing_counts = Counter()
    columns = None
    label_column = None
    data_types = {}

    for chunk in pd.read_csv(file_path, chunksize=CHUNK_SIZE):
        if columns is None:
            columns = list(chunk.columns)

            label_matches = [
                col for col in columns
                if col.strip().lower() == "label"
            ]

            if not label_matches:
                raise ValueError(
                    f"No Label column found in {file_path.name}. "
                    f"Columns: {columns}"
                )

            label_column = label_matches[0]
            data_types = {
                col: str(dtype)
                for col, dtype in chunk.dtypes.items()
            }

        elif list(chunk.columns) != columns:
            raise ValueError(
                f"Column mismatch found in {file_path.name}"
            )

        total_rows += len(chunk)

        missing = chunk.isna().sum()
        for col, count in missing.items():
            missing_counts[col] += int(count)

        labels = chunk[label_column].astype("string").fillna("<MISSING>")
        label_counts.update(labels.value_counts().to_dict())

    report = {
        "file": file_path.name,
        "rows": total_rows,
        "columns": len(columns),
        "feature_count": len(columns) - 1,
        "label_column": label_column,
        "class_count": len(label_counts) - (
            1 if "<MISSING>" in label_counts else 0
        ),
        "class_distribution": dict(label_counts.most_common()),
        "missing_values": dict(missing_counts),
        "data_types": data_types,
        "column_names": columns,
    }

    print(f"Rows: {total_rows:,}")
    print(f"Columns: {len(columns)}")
    print(f"Features: {len(columns) - 1}")
    print(f"Classes: {report['class_count']}")
    print("Class distribution:")

    for label, count in label_counts.most_common():
        print(f"  {label}: {count:,}")

    missing_total = sum(missing_counts.values())
    print(f"Missing values: {missing_total:,}")

    return report


def main():
    reports = {}

    for name, file_path in FILES.items():
        reports[name] = inspect_csv(name, file_path)

    output_path = Path("dataset_report.json")

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(reports, f, indent=2)

    print(f"\nInspection completed.")
    print(f"Report saved to: {output_path.resolve()}")


if __name__ == "__main__":
    main()
