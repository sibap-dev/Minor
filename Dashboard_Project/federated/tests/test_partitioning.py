import numpy as np
import pytest

from greenfed_fl.partitioning import (
    PartitionConfig,
    class_share_std,
    create_dirichlet_partition,
    create_iid_partition,
    create_partition,
    load_partition_report,
    read_partition_indices,
    summarise_partition,
    validate_partition,
    write_partition,
)


def synthetic_labels():
    rng = np.random.default_rng(0)
    classes = ["A", "B", "C", "D"]
    return np.array([classes[i] for i in rng.integers(0, 4, size=200)])


def test_iid_covers_every_row_once():
    labels = synthetic_labels()
    config = PartitionConfig(num_clients=5, method="iid", seed=42)
    partitions = create_iid_partition(labels, config)
    result = validate_partition(partitions, len(labels))
    assert result["all_records_assigned_once"]
    assert result["duplicate_indices_across_clients"] == 0
    assert result["indices_in_valid_range"]
    assert result["test_split_used"] is False
    assert result["empty_clients"] == []


def test_dirichlet_covers_every_row_once():
    labels = synthetic_labels()
    config = PartitionConfig(num_clients=5, method="non_iid", alpha=0.5, seed=42)
    partitions = create_dirichlet_partition(labels, config)
    result = validate_partition(partitions, len(labels))
    assert result["all_records_assigned_once"]
    assert len(partitions) == 5


@pytest.mark.parametrize("method", ["iid", "non_iid"])
def test_partition_is_reproducible(method):
    labels = synthetic_labels()
    config = PartitionConfig(num_clients=5, method=method, alpha=0.5, seed=7)
    first = create_partition(labels, config)
    second = create_partition(labels, config)
    for a, b in zip(first, second):
        assert np.array_equal(a, b)


def test_different_seed_changes_assignment():
    labels = synthetic_labels()
    first = create_partition(
        labels, PartitionConfig(num_clients=3, method="iid", seed=1)
    )
    second = create_partition(
        labels, PartitionConfig(num_clients=3, method="iid", seed=2)
    )
    assert any(not np.array_equal(a, b) for a, b in zip(first, second))


def test_configured_client_count():
    labels = synthetic_labels()
    config = PartitionConfig(num_clients=7, method="iid", seed=42)
    partitions = create_partition(labels, config)
    assert len(partitions) == 7
    assert validate_partition(partitions, len(labels))["all_records_assigned_once"]


def test_report_roundtrip(tmp_path):
    labels = synthetic_labels()
    config = PartitionConfig(num_clients=4, method="non_iid", alpha=0.3, seed=11)
    partitions = create_partition(labels, config)
    report = write_partition(partitions, labels, tmp_path, config)

    assert report["dirichlet_alpha"] == 0.3
    assert report["random_seed"] == 11
    assert report["all_records_assigned_once"]
    assert report["test_set_used_for_partitioning"] is False

    loaded = load_partition_report(tmp_path)
    assert loaded["number_of_clients"] == 4
    indices = read_partition_indices(tmp_path)
    assert len(indices) == 4
    assert np.array_equal(np.sort(np.concatenate(indices)), np.arange(len(labels)))


def test_write_refuses_overwrite_without_flag(tmp_path):
    labels = synthetic_labels()
    config = PartitionConfig(num_clients=2, method="iid", seed=1)
    write_partition(create_partition(labels, config), labels, tmp_path, config)
    with pytest.raises(FileExistsError):
        write_partition(create_partition(labels, config), labels, tmp_path, config)


def test_iid_has_lower_class_share_spread_than_dirichlet():
    labels = synthetic_labels()
    iid_report = summarise_partition(
        create_partition(labels, PartitionConfig(5, "iid", seed=3)), labels
    )
    non_report = summarise_partition(
        create_partition(labels, PartitionConfig(5, "non_iid", 0.1, seed=3)), labels
    )
    iid_report = {"clients": iid_report}
    non_report = {"clients": non_report}
    assert class_share_std(iid_report) < class_share_std(non_report)


def test_invalid_config_rejected():
    with pytest.raises(ValueError):
        PartitionConfig(num_clients=0)
    with pytest.raises(ValueError):
        PartitionConfig(method="unknown")
    with pytest.raises(ValueError):
        PartitionConfig(method="non_iid", alpha=0.0)
