
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PARTITION_DIR = PROJECT_ROOT / "output" / "partitions"


def inspect(method):
    report_path = (
        PARTITION_DIR / method / "partition_report.json"
    )

    with open(report_path, encoding="utf-8") as file:
        report = json.load(file)

    print(f"\n{'=' * 55}")
    print(f"{method.upper()} PARTITION")
    print(f"{'=' * 55}")

    total = report["total_training_records"]

    for client, details in report["clients"].items():
        records = details["records"]
        percentage = records / total * 100

        print(
            f"{client}: "
            f"{records:,} records | "
            f"{percentage:.2f}% | "
            f"{details['class_count']} classes"
        )

    print(
        "\nAll records assigned exactly once:",
        report["all_records_assigned_once"]
    )


if __name__ == "__main__":
    inspect("iid")
    inspect("non_iid")
