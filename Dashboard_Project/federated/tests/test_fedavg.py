import numpy as np
import torch

from greenfed_fl.context import ClientContext
from greenfed_fl.data import ClientData, FederatedData
from greenfed_fl.fedavg import (
    TrainConfig,
    aggregate_state_dicts,
    evaluate,
    predict,
    run_federated_experiment,
    train_local,
)
from greenfed_fl.model import ModelConfig, model_parameter_count, model_state_bytes
from greenfed_fl.selection import SelectionConfig, select_clients


def synthetic_federated_data(seed=0):
    rng = np.random.default_rng(seed)
    n_features = 4
    classes = ["A", "B", "C"]
    clients = []
    for client_id in range(1, 6):
        n = 60
        X = rng.normal(size=(n, n_features)).astype(np.float32)
        y = rng.integers(0, len(classes), size=n).astype(np.int64)
        clients.append(
            ClientData(
                client_id=client_id,
                X=X,
                y=y,
                source_indices=np.arange(n, dtype=np.int64),
            )
        )
    val_X = np.concatenate([client.X for client in clients], axis=0)
    val_y = np.concatenate([client.y for client in clients], axis=0)
    return FederatedData(
        clients=clients,
        val_X=val_X,
        val_y=val_y,
        classes=classes,
        feature_names=[f"f{i}" for i in range(n_features)],
        scaler_mean=np.zeros(n_features, dtype=np.float32),
        scaler_scale=np.ones(n_features, dtype=np.float32),
        metadata={"synthetic": True},
    )


def synthetic_contexts():
    return [
        ClientContext(
            client_id=f"client_{i}",
            cpu_percent=20.0 + 10 * i,
            memory_percent=40.0,
            memory_available_mb=2048.0,
            disk_percent=50.0,
            latency_ms=20.0 + 30 * i,
            packet_loss_percent=1.0,
            bandwidth_mbps=80.0 - 10 * i,
            jitter_ms=4.0,
            availability=0.95,
            local_samples=60,
            class_coverage=3,
            total_classes=3,
            provenance={name: "simulated" for name in [
                "cpu_percent", "memory_percent", "memory_available_mb",
                "disk_percent", "latency_ms", "packet_loss_percent",
                "bandwidth_mbps", "jitter_ms", "availability",
            ]},
        )
        for i in range(1, 6)
    ]


def test_model_shape_and_parameter_count():
    model = ModelConfig(input_dim=39, num_classes=34).build()
    output = model(torch.zeros(5, 39))
    assert tuple(output.shape) == (5, 34)
    expected = 39 * 128 + 128 + 128 * 64 + 64 + 64 * 34 + 34
    assert model_parameter_count(model) == expected
    assert model_state_bytes(model) == expected * 4


def test_aggregate_weighted_average():
    states = [
        {"w": torch.tensor([1.0, 3.0])},
        {"w": torch.tensor([5.0, 7.0])},
    ]
    aggregated = aggregate_state_dicts(states, [1.0, 3.0])
    assert torch.allclose(aggregated["w"], torch.tensor([4.0, 6.0]))


def test_train_local_returns_metrics_and_state():
    data = synthetic_federated_data()
    config = ModelConfig(input_dim=4, num_classes=3)
    global_model = config.build()
    state = global_model.state_dict()
    train_config = TrainConfig(rounds=1, local_epochs=1, batch_size=16, num_threads=1)
    local_state, metrics = train_local(
        state, config, data.clients[0], train_config, None, round_number=1
    )
    assert set(local_state) == set(state)
    assert metrics["local_samples"] == 60
    assert metrics["duration_seconds"] >= 0
    assert metrics["mean_batch_loss"] is not None


def test_predict_and_evaluate_shapes():
    data = synthetic_federated_data()
    config = ModelConfig(input_dim=4, num_classes=3)
    model = config.build()
    predictions = predict(model, data.val_X)
    assert predictions.shape == (len(data.val_y),)
    metrics = evaluate(model.state_dict(), config, data.val_X, data.val_y, data.classes)
    assert metrics["samples_evaluated"] == len(data.val_y)
    assert 0.0 <= metrics["accuracy"] <= 1.0


def test_run_federated_experiment_all_strategies():
    data = synthetic_federated_data()
    contexts = synthetic_contexts()
    train_config = TrainConfig(
        rounds=1, local_epochs=1, batch_size=16, seed=3, num_threads=1
    )
    selection_config = SelectionConfig(num_select=2)

    for strategy in ["all", "random", "resource", "context"]:
        results = run_federated_experiment(
            data=data,
            contexts=[ClientContext.from_dict(c.to_dict()) for c in contexts],
            strategy=strategy,
            selection_config=selection_config,
            train_config=train_config,
            select_fn=select_clients,
            scenario="synthetic",
            test_X=data.val_X,
            test_y=data.val_y,
            log=lambda *_: None,
        )
        assert results["strategy"] == strategy
        assert len(results["rounds"]) == 1
        assert results["test"] is not None
        assert results["resource_summary"]["communication_bytes_total"] > 0
        assert len(results["rounds"][0]["selected_clients"]) == (
            5 if strategy == "all" else 2
        )
