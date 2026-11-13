import numpy as np
import pytest

from greenfed_fl.context import ClientContext, generate_simulated_context
from greenfed_fl.metrics import evaluate_predictions


def synthetic_partition_report():
    return {
        "number_of_classes": 3,
        "clients": {
            "client_1": {
                "records": 100,
                "class_count": 3,
                "class_distribution": {"A": 50, "B": 30, "C": 20},
            },
            "client_2": {
                "records": 80,
                "class_count": 2,
                "class_distribution": {"A": 10, "B": 70},
            },
        },
    }


def test_generate_context_uses_real_sample_counts_and_labels_provenance():
    clients, metadata = generate_simulated_context(
        synthetic_partition_report(), seed=1, jitter=False
    )
    assert metadata["provenance"] == "simulated"
    assert clients[0].local_samples == 100
    assert clients[0].class_coverage == 3
    assert clients[1].class_coverage == 2
    assert clients[0].provenance["cpu_percent"] == "simulated"
    assert clients[0].provenance["local_samples"] == "measured"


def test_generate_context_is_reproducible():
    first, _ = generate_simulated_context(synthetic_partition_report(), seed=9)
    second, _ = generate_simulated_context(synthetic_partition_report(), seed=9)
    assert [c.to_dict() for c in first] == [c.to_dict() for c in second]


def test_invalid_context_rejected():
    with pytest.raises(ValueError):
        ClientContext(client_id="bad", cpu_percent=150.0)
    with pytest.raises(ValueError):
        ClientContext(client_id="bad", packet_loss_percent=101.0)
    with pytest.raises(ValueError):
        ClientContext(client_id="", cpu_percent=10.0)


def test_missing_metric_gets_unavailable_provenance():
    client = ClientContext(client_id="c1", cpu_percent=None, latency_ms=None)
    assert client.provenance["cpu_percent"] == "unavailable"
    assert client.provenance["latency_ms"] == "unavailable"


def test_metrics_known_values():
    y_true = np.array([0, 1, 1, 2])
    y_pred = np.array([0, 1, 2, 2])
    metrics = evaluate_predictions(y_true, y_pred, ["A", "B", "C"])
    assert metrics["samples_evaluated"] == 4
    assert metrics["accuracy"] == pytest.approx(0.75)
    assert metrics["per_class"]["C"]["support"] == 1
    assert len(metrics["confusion_matrix"]) == 3
    assert metrics["unknown_label_samples_excluded"] == 0


def test_metrics_exclude_unknown_labels():
    y_true = np.array([0, 1, -1])
    y_pred = np.array([0, 1, 2])
    metrics = evaluate_predictions(y_true, y_pred, ["A", "B", "C"])
    assert metrics["samples_evaluated"] == 2
    assert metrics["unknown_label_samples_excluded"] == 1
