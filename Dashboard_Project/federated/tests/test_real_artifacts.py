from pathlib import Path

import numpy as np
import pytest

from greenfed_fl.partitioning import (
    class_share_std,
    load_partition_report,
    read_partition_indices,
    validate_partition,
)
from greenfed_fl.paths import PARTITIONS_DIR, TRAIN_CSV


pytestmark = pytest.mark.skipif(
    not TRAIN_CSV.is_file() or not PARTITIONS_DIR.exists(),
    reason="Real dataset or partition artifacts are not available",
)


@pytest.fixture(scope="module")
def training_labels():
    import pandas as pd

    return (
        pd.read_csv(TRAIN_CSV, usecols=["Label"])["Label"]
        .astype(str)
        .str.strip()
        .to_numpy()
    )


def test_real_partitions_cover_every_training_row(training_labels):
    for method in ["iid", "non_iid"]:
        indices = read_partition_indices(PARTITIONS_DIR / method)
        result = validate_partition(indices, len(training_labels))
        assert result["all_records_assigned_once"], method
        assert result["duplicate_indices_across_clients"] == 0, method
        assert result["indices_in_valid_range"], method
        assert max(part.max() for part in indices) < len(training_labels)


def test_known_five_client_allocations_preserved():
    expected = {
        "iid": [234019, 234012, 234003, 233997, 233991],
        "non_iid": [220029, 232318, 271630, 325213, 120832],
    }
    for method, counts in expected.items():
        report = load_partition_report(PARTITIONS_DIR / method)
        actual = [report["clients"][f"client_{i}"]["records"] for i in range(1, 6)]
        assert actual == counts
        assert report["random_seed"] == 42
        if method == "non_iid":
            assert report["dirichlet_alpha"] == 0.5


def test_iid_less_heterogeneous_than_non_iid():
    iid = load_partition_report(PARTITIONS_DIR / "iid")
    non_iid = load_partition_report(PARTITIONS_DIR / "non_iid")
    assert class_share_std(iid) < class_share_std(non_iid)
