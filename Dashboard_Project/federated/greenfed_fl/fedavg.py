"""Federated Averaging training, aggregation and evaluation."""

from __future__ import annotations

import copy
import math
import os
import time
from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np
import psutil
import torch
from torch import nn

from .context import ClientContext
from .data import ClientData, FederatedData
from .metrics import evaluate_predictions
from .model import GreenFedMLP, ModelConfig, model_parameter_count, model_state_bytes
from .selection import (
    SelectionConfig,
    SelectionResult,
    update_participation,
)


@dataclass
class TrainConfig:
    rounds: int = 2
    local_epochs: int = 1
    batch_size: int = 256
    learning_rate: float = 0.001
    seed: int = 42
    class_weight_mode: str = "none"  # "none" | "balanced"
    num_threads: int = 4

    def validate(self) -> None:
        if self.rounds < 1:
            raise ValueError("rounds must be >= 1")
        if self.local_epochs < 1:
            raise ValueError("local_epochs must be >= 1")
        if self.batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if self.class_weight_mode not in {"none", "balanced"}:
            raise ValueError("class_weight_mode must be 'none' or 'balanced'")


def set_determinism(seed: int, num_threads: int = 4) -> None:
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.set_num_threads(max(1, num_threads))
    os.environ.setdefault("PYTHONHASHSEED", str(seed))


def _client_class_counts(data: FederatedData) -> np.ndarray:
    counts = np.zeros(len(data.classes), dtype=np.int64)
    for client in data.clients:
        for index, count in client.class_counts().items():
            counts[index] += count
    return counts


def federated_class_weights(data: FederatedData) -> np.ndarray | None:
    """Balanced weights from aggregated label counts (no raw data transfer)."""

    counts = _client_class_counts(data).astype(np.float64)
    if counts.sum() == 0:
        return None
    counts[counts == 0] = 1.0
    weights = counts.sum() / (len(counts) * counts)
    return weights.astype(np.float32)


def _to_tensor(array: np.ndarray, dtype: torch.dtype) -> torch.Tensor:
    return torch.from_numpy(np.ascontiguousarray(array)).to(dtype)


def train_local(
    global_state: dict,
    model_config: ModelConfig,
    client: ClientData,
    train_config: TrainConfig,
    class_weights: np.ndarray | None,
    round_number: int,
) -> tuple[dict, dict]:
    """Train one local model and return its state dict and runtime metrics."""

    process = psutil.Process()
    cpu_before = sum(process.cpu_times()[:2])
    start = time.perf_counter()

    model = model_config.build()
    model.load_state_dict(global_state)
    model.train()

    optimizer = torch.optim.Adam(model.parameters(), lr=train_config.learning_rate)
    weight_tensor = (
        torch.from_numpy(class_weights)
        if class_weights is not None
        else None
    )
    criterion = nn.CrossEntropyLoss(weight=weight_tensor)

    X = _to_tensor(client.X, torch.float32)
    y = _to_tensor(client.y, torch.int64)
    n = len(y)

    generator = torch.Generator().manual_seed(
        train_config.seed + round_number * 1000 + client.client_id
    )

    total_loss = 0.0
    batches = 0

    for _ in range(train_config.local_epochs):
        permutation = torch.randperm(n, generator=generator)
        for start_index in range(0, n, train_config.batch_size):
            batch_indices = permutation[start_index:start_index + train_config.batch_size]
            if len(batch_indices) < 2:
                continue
            optimizer.zero_grad(set_to_none=True)
            logits = model(X[batch_indices])
            loss = criterion(logits, y[batch_indices])
            loss.backward()
            optimizer.step()
            total_loss += float(loss.detach())
            batches += 1

    duration = time.perf_counter() - start
    cpu_after = sum(process.cpu_times()[:2])
    rss_mb = process.memory_info().rss / (1024 ** 2)

    state = {name: tensor.detach().cpu().clone() for name, tensor in model.state_dict().items()}
    metrics = {
        "client_id": f"client_{client.client_id}",
        "local_samples": int(n),
        "epochs": train_config.local_epochs,
        "batches": batches,
        "mean_batch_loss": float(total_loss / batches) if batches else None,
        "duration_seconds": float(duration),
        "cpu_seconds": float(cpu_after - cpu_before),
        "process_rss_mb_after": float(rss_mb),
        "resource_scope": "host_training_process",
    }
    return state, metrics


def aggregate_state_dicts(
    states: Sequence[dict], weights: Sequence[float]
) -> dict:
    if not states:
        raise ValueError("No client updates to aggregate")
    if len(states) != len(weights):
        raise ValueError("states and weights length mismatch")
    total = float(sum(weights))
    if total <= 0:
        raise ValueError("Aggregation weights must sum to a positive value")

    aggregated = {}
    for name in states[0]:
        tensors = [state[name] for state in states]
        if not torch.is_floating_point(tensors[0]):
            aggregated[name] = tensors[0].clone()
            continue
        stacked = torch.stack(
            [tensor.to(torch.float64) * (weight / total) for tensor, weight in zip(tensors, weights)]
        )
        aggregated[name] = stacked.sum(dim=0).to(tensors[0].dtype)
    return aggregated


def predict(
    model: nn.Module,
    X: np.ndarray,
    batch_size: int = 8192,
) -> np.ndarray:
    model.eval()
    predictions = []
    with torch.no_grad():
        for start in range(0, len(X), batch_size):
            chunk = torch.from_numpy(
                np.ascontiguousarray(X[start:start + batch_size])
            ).float()
            logits = model(chunk)
            predictions.append(torch.argmax(logits, dim=1).numpy())
    if not predictions:
        return np.empty((0,), dtype=np.int64)
    return np.concatenate(predictions)


def evaluate(
    global_state: dict,
    model_config: ModelConfig,
    X: np.ndarray,
    y: np.ndarray,
    classes: Sequence[str],
) -> dict:
    if len(y) == 0:
        return {"samples_evaluated": 0, "note": "empty evaluation set"}
    model = model_config.build()
    model.load_state_dict(global_state)
    predictions = predict(model, X)
    return evaluate_predictions(y, predictions, list(classes))


def run_federated_experiment(
    data: FederatedData,
    contexts: Sequence[ClientContext],
    strategy: str,
    selection_config: SelectionConfig,
    train_config: TrainConfig,
    select_fn: Callable,
    scenario: str,
    test_X: np.ndarray | None = None,
    test_y: np.ndarray | None = None,
    selection_override: SelectionResult | None = None,
    log: Callable[[str], None] = print,
) -> dict:
    """Execute a complete federated run and return JSON-serialisable results.

    When ``selection_override`` is supplied, the exact selected client IDs are
    reused for every round instead of calling the selector again.  This is the
    dashboard hand-off path: the participant set inspected by the user is the
    participant set trained in the run.
    """

    train_config.validate()
    set_determinism(train_config.seed, train_config.num_threads)

    model_config = ModelConfig(
        input_dim=len(data.feature_names),
        num_classes=len(data.classes),
    )
    global_model = model_config.build()
    global_state = {
        name: tensor.detach().cpu().clone()
        for name, tensor in global_model.state_dict().items()
    }

    class_weights = (
        federated_class_weights(data)
        if train_config.class_weight_mode == "balanced"
        else None
    )

    context_by_id = {context.client_id: context for context in contexts}
    clients_by_id = {f"client_{client.client_id}": client for client in data.clients}

    missing_context = set(clients_by_id) - set(context_by_id)
    if missing_context:
        raise ValueError(f"Missing context for clients: {sorted(missing_context)}")

    state_bytes = model_state_bytes(global_model)
    rounds_log = []
    cumulative_comm_bytes = 0.0
    cumulative_cpu_seconds = 0.0
    cumulative_train_seconds = 0.0

    for round_number in range(1, train_config.rounds + 1):
        round_start = time.perf_counter()
        if selection_override is not None:
            selection = copy.deepcopy(selection_override)
            selection.round_number = round_number
            selection.notes = list(selection.notes) + [
                "Dashboard selection reused for this round without reselection."
            ]
        else:
            selection = select_fn(
                list(contexts),
                strategy=strategy,
                config=selection_config,
                seed=train_config.seed,
                round_number=round_number,
            )

        selected_clients = [
            clients_by_id[cid] for cid in selection.selected if cid in clients_by_id
        ]
        if not selected_clients:
            raise RuntimeError(f"No trainable clients selected in round {round_number}")

        log(
            f"[round {round_number}] strategy={strategy} "
            f"selected={selection.selected} relaxed={selection.constraints_relaxed}"
        )

        states = []
        weights = []
        client_metrics = []
        for client in selected_clients:
            state, metrics = train_local(
                global_state,
                model_config,
                client,
                train_config,
                class_weights,
                round_number,
            )
            states.append(state)
            weights.append(float(client.n_samples))
            client_metrics.append(metrics)
            log(
                f"    {metrics['client_id']}: loss={metrics['mean_batch_loss']:.4f} "
                f"time={metrics['duration_seconds']:.1f}s"
            )

        global_state = aggregate_state_dicts(states, weights)

        val_metrics = evaluate(
            global_state, model_config, data.val_X, data.val_y, data.classes
        )

        update_participation(contexts, selection.selected)

        round_comm_bytes = float(state_bytes * 2 * len(selected_clients))
        round_cpu = float(sum(item["cpu_seconds"] for item in client_metrics))
        round_train = float(sum(item["duration_seconds"] for item in client_metrics))
        round_duration = time.perf_counter() - round_start

        cumulative_comm_bytes += round_comm_bytes
        cumulative_cpu_seconds += round_cpu
        cumulative_train_seconds += round_train

        rounds_log.append(
            {
                "round": round_number,
                "selected_clients": selection.selected,
                "selection": selection.to_dict(),
                "local_training": client_metrics,
                "validation": val_metrics,
                "communication_bytes_round": round_comm_bytes,
                "communication_bytes_cumulative": cumulative_comm_bytes,
                "cpu_seconds_round": round_cpu,
                "training_seconds_round": round_train,
                "wall_seconds_round": float(round_duration),
                "model_state_bytes": state_bytes,
            }
        )

    final_validation = rounds_log[-1]["validation"]

    test_metrics = None
    if test_X is not None and test_y is not None:
        log("[final] evaluating held-out test set")
        test_metrics = evaluate(
            global_state, model_config, test_X, test_y, data.classes
        )

    results = {
        "scenario": scenario,
        "strategy": strategy,
        "model": {
            "architecture": "MLP 39->128->64->34 (ReLU)",
            "parameter_count": model_parameter_count(global_model),
            "state_bytes": state_bytes,
        },
        "configuration": {
            "rounds": train_config.rounds,
            "local_epochs": train_config.local_epochs,
            "batch_size": train_config.batch_size,
            "learning_rate": train_config.learning_rate,
            "seed": train_config.seed,
            "class_weight_mode": train_config.class_weight_mode,
            "num_threads": train_config.num_threads,
            "optimizer": "Adam",
            "aggregation": "sample-weighted FedAvg",
            "selection_source": (
                "fixed_dashboard_selection"
                if selection_override is not None
                else "algorithmic_reselection_each_round"
            ),
            "num_select": selection_config.num_select,
            "participants_per_round": [
                len(round_data["selected_clients"]) for round_data in rounds_log
            ],
            "eligibility": {
                "min_availability": selection_config.min_availability,
                "max_cpu_percent": selection_config.max_cpu_percent,
                "min_memory_available_mb": selection_config.min_memory_available_mb,
                "max_disk_percent": selection_config.max_disk_percent,
                "max_latency_ms": selection_config.max_latency_ms,
                "max_packet_loss_percent": selection_config.max_packet_loss_percent,
            },
            "selection_weights": (
                dict(selection_config.weights)
                if strategy == "context"
                else "resource-only" if strategy == "resource" else "n/a"
            ),
        },
        "data": data.metadata,
        "rounds": rounds_log,
        "final_validation": final_validation,
        "test": test_metrics,
        "resource_summary": {
            "communication_bytes_total": cumulative_comm_bytes,
            "communication_megabytes_total": cumulative_comm_bytes / (1024 ** 2),
            "cpu_seconds_total": cumulative_cpu_seconds,
            "training_seconds_total": cumulative_train_seconds,
            "resource_scope": "host_training_process",
            "energy_measured": False,
            "energy_note": (
                "No energy meter is available. CPU seconds and communication "
                "volume are reported as measured/computed sustainability proxies."
            ),
        },
    }
    return results
