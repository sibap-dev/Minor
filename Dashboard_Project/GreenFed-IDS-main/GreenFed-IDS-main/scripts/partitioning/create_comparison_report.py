
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PARTITION_DIR = PROJECT_ROOT / "output" / "partitions"

with open(
    PARTITION_DIR / "iid" / "partition_report.json",
    encoding="utf-8"
) as f:
    iid = json.load(f)

with open(
    PARTITION_DIR / "non_iid" / "partition_report.json",
    encoding="utf-8"
) as f:
    non_iid = json.load(f)


def get_client_summary(report):
    result = {}

    for client, details in report["clients"].items():
        result[client] = {
            "records": details["records"],
            "percentage": round(
                details["records"]
                / report["total_training_records"] * 100,
                2
            ),
            "classes": details["class_count"]
        }

    return result


comparison = {
    "dataset": "CICIoT2023",
    "training_records": iid["total_training_records"],
    "testing_records": 290874,
    "features": 39,
    "number_of_classes": 34,
    "number_of_clients": 5,
    "random_seed": 42,
    "iid": {
        "validation": iid["all_records_assigned_once"],
        "clients": get_client_summary(iid)
    },
    "non_iid": {
        "validation": non_iid["all_records_assigned_once"],
        "dirichlet_alpha": 0.5,
        "clients": get_client_summary(non_iid)
    },
    "test_set_used_for_partitioning": False,
    "fedavg_code_modified": False
}

output_file = PROJECT_ROOT / "output" / "partitions" / "comparison_report.json"

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(comparison, f, indent=4)

print("Comparison report created successfully:")
print(output_file)
