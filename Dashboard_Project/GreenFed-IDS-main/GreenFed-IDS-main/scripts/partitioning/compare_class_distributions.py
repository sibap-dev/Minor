
import json
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PARTITION_DIR = PROJECT_ROOT / "output" / "partitions"


def load_report(method):
    path = PARTITION_DIR / method / "partition_report.json"

    with open(path, encoding="utf-8") as file:
        return json.load(file)


iid = load_report("iid")
non_iid = load_report("non_iid")


def make_dataframe(report):
    rows = {}

    for client, details in report["clients"].items():
        rows[client] = details["class_distribution"]

    return pd.DataFrame(rows).fillna(0).astype(int)


iid_df = make_dataframe(iid)
non_iid_df = make_dataframe(non_iid)

print("\nIID CLASS DISTRIBUTION (first 10 classes)")
print(iid_df.head(10).to_string())

print("\nNON-IID CLASS DISTRIBUTION (first 10 classes)")
print(non_iid_df.head(10).to_string())


# Calculate percentage of each class assigned to each client.
def make_percentage_dataframe(df):
    return df.div(df.sum(axis=1), axis=0) * 100


iid_pct = make_percentage_dataframe(iid_df)
non_iid_pct = make_percentage_dataframe(non_iid_df)

# Compare how differently each class is distributed.
iid_variation = iid_pct.std(axis=1)
non_iid_variation = non_iid_pct.std(axis=1)

comparison = pd.DataFrame({
    "IID_percentage_std": iid_variation,
    "Non_IID_percentage_std": non_iid_variation
})

comparison["difference"] = (
    comparison["Non_IID_percentage_std"]
    - comparison["IID_percentage_std"]
)

comparison = comparison.sort_values(
    "difference",
    ascending=False
)

print("\nMOST UNEVENLY DISTRIBUTED CLASSES IN NON-IID")
print(comparison.head(10).round(2).to_string())

print("\nAverage class-wise percentage standard deviation:")
print(f"IID: {iid_variation.mean():.2f}")
print(f"Non-IID: {non_iid_variation.mean():.2f}")
