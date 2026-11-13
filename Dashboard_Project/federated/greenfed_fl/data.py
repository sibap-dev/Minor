"""Data loading, class mapping, scaling and client construction.

Only the training CSV is used to fit preprocessing and to build clients.  The
held-out test CSV is loaded only for final evaluation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from .paths import LABEL_COLUMN, require_file


@dataclass
class ClientData:
    client_id: int
    X: np.ndarray
    y: np.ndarray
    source_indices: np.ndarray

    @property
    def n_samples(self) -> int:
        return int(len(self.y))

    def class_counts(self) -> dict[int, int]:
        values, counts = np.unique(self.y, return_counts=True)
        return {int(v): int(c) for v, c in zip(values, counts)}


@dataclass
class FederatedData:
    clients: list[ClientData]
    val_X: np.ndarray
    val_y: np.ndarray
    classes: list[str]
    feature_names: list[str]
    scaler_mean: np.ndarray
    scaler_scale: np.ndarray
    metadata: dict = field(default_factory=dict)

    @property
    def class_to_index(self) -> dict[str, int]:
        return {name: index for index, name in enumerate(self.classes)}


def feature_columns_from_header(csv_path: str | Path) -> list[str]:
    path = require_file(Path(csv_path), "Training CSV")
    header = pd.read_csv(path, nrows=0).columns.tolist()
    if LABEL_COLUMN not in header:
        raise ValueError(f"Label column '{LABEL_COLUMN}' not found in {path}")
    features = [name for name in header if name != LABEL_COLUMN]
    if not features:
        raise ValueError("No feature columns found")
    return features


def load_training_data(
    csv_path: str | Path,
    feature_columns: Sequence[str] | None = None,
) -> tuple[np.ndarray, np.ndarray, list[str], list[str]]:
    """Return X (float32), y (int64), class names, feature names.

    Memory note: the full 39-feature training split is roughly 183 MB in
    float32.  The caller is responsible for releasing X after client arrays are
    built.
    """

    path = require_file(Path(csv_path), "Training CSV")
    header = pd.read_csv(path, nrows=0).columns.tolist()
    if LABEL_COLUMN not in header:
        raise ValueError(f"Label column '{LABEL_COLUMN}' missing")

    features = list(feature_columns) if feature_columns else [
        name for name in header if name != LABEL_COLUMN
    ]
    missing = [name for name in features if name not in header]
    if missing:
        raise ValueError(f"Requested features missing from CSV: {missing}")

    dtype_map = {name: np.float32 for name in features}
    frame = pd.read_csv(path, usecols=features + [LABEL_COLUMN], dtype=dtype_map)

    labels = frame[LABEL_COLUMN].astype(str).str.strip()
    if labels.isna().any():
        raise ValueError("Missing labels in training data")

    X = frame[features].to_numpy(dtype=np.float32, copy=True)
    del frame

    if not np.isfinite(X).all():
        raise ValueError("Non-finite values found in training features")

    classes = sorted(labels.unique().tolist())
    class_to_index = {name: index for index, name in enumerate(classes)}
    y = labels.map(class_to_index).to_numpy(dtype=np.int64)

    return X, y, classes, features


def load_test_data(
    csv_path: str | Path,
    feature_columns: Sequence[str],
    classes: Sequence[str],
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Load the held-out test split and encode labels with the training map."""

    path = require_file(Path(csv_path), "Test CSV")
    header = pd.read_csv(path, nrows=0).columns.tolist()
    missing = [name for name in feature_columns if name not in header]
    if missing:
        raise ValueError(f"Test CSV missing features: {missing}")
    if LABEL_COLUMN not in header:
        raise ValueError("Test CSV missing Label column")

    dtype_map = {name: np.float32 for name in feature_columns}
    frame = pd.read_csv(path, usecols=list(feature_columns) + [LABEL_COLUMN], dtype=dtype_map)
    labels = frame[LABEL_COLUMN].astype(str).str.strip()

    class_to_index = {name: index for index, name in enumerate(classes)}
    encoded = labels.map(class_to_index)
    unknown = labels[encoded.isna()].value_counts().to_dict()
    encoded = encoded.fillna(-1).to_numpy(dtype=np.int64)
    X = frame[list(feature_columns)].to_numpy(dtype=np.float32, copy=True)
    del frame

    if not np.isfinite(X).all():
        raise ValueError("Non-finite values found in test features")

    metadata = {"test_rows": int(len(labels)), "unknown_test_labels": unknown}
    return X, encoded, metadata


def build_clients(
    X: np.ndarray,
    y: np.ndarray,
    partitions: Sequence[np.ndarray],
    max_samples_per_client: int | None = None,
    seed: int = 42,
) -> tuple[list[ClientData], dict]:
    """Materialise per-client arrays from partition indices.

    Subsampling, when enabled, is deterministic per client and is recorded in
    the returned metadata.
    """

    rng = np.random.default_rng(seed)
    clients: list[ClientData] = []
    metadata = {"max_samples_per_client": max_samples_per_client, "clients": {}}

    for client_id, indices in enumerate(partitions, start=1):
        indices = np.asarray(indices, dtype=np.int64)
        requested = int(len(indices))
        if max_samples_per_client and requested > max_samples_per_client:
            indices = np.sort(
                rng.choice(indices, size=max_samples_per_client, replace=False)
            )
        clients.append(
            ClientData(
                client_id=client_id,
                X=X[indices].copy(),
                y=y[indices].copy(),
                source_indices=indices,
            )
        )
        metadata["clients"][f"client_{client_id}"] = {
            "partition_records": requested,
            "used_records": int(len(indices)),
            "subsampled": requested != int(len(indices)),
        }

    return clients, metadata


def split_validation(
    clients: Sequence[ClientData],
    validation_fraction: float,
    seed: int = 42,
) -> tuple[list[ClientData], np.ndarray, np.ndarray, dict]:
    """Hold out a deterministic fraction of each client's local data.

    Validation samples are drawn from the training split only.  The held-out
    test CSV is never touched.
    """

    if not (0.0 <= validation_fraction < 1.0):
        raise ValueError("validation_fraction must be in [0, 1)")

    rng = np.random.default_rng(seed + 1000)
    train_clients: list[ClientData] = []
    val_X_parts: list[np.ndarray] = []
    val_y_parts: list[np.ndarray] = []
    details = {}

    for client in clients:
        n = client.n_samples
        if validation_fraction <= 0 or n < 2:
            n_val = 0
        else:
            n_val = max(1, int(round(n * validation_fraction)))
            n_val = min(n_val, n - 1)

        permutation = rng.permutation(n)
        val_idx = permutation[:n_val]
        train_idx = permutation[n_val:]

        train_clients.append(
            ClientData(
                client_id=client.client_id,
                X=client.X[train_idx],
                y=client.y[train_idx],
                source_indices=client.source_indices[train_idx],
            )
        )
        if n_val:
            val_X_parts.append(client.X[val_idx])
            val_y_parts.append(client.y[val_idx])

        details[f"client_{client.client_id}"] = {
            "train_records": int(len(train_idx)),
            "validation_records": int(n_val),
        }

    if val_X_parts:
        val_X = np.concatenate(val_X_parts, axis=0)
        val_y = np.concatenate(val_y_parts, axis=0)
    else:
        val_X = np.empty((0, clients[0].X.shape[1]), dtype=np.float32)
        val_y = np.empty((0,), dtype=np.int64)

    return train_clients, val_X, val_y, details


def fit_scaler(
    arrays: Iterable[np.ndarray], chunk_size: int = 100_000
) -> tuple[np.ndarray, np.ndarray]:
    """Fit a StandardScaler on chunks without materialising a full copy."""

    scaler = StandardScaler()
    seen = False
    for array in arrays:
        for start in range(0, len(array), chunk_size):
            chunk = array[start:start + chunk_size]
            if len(chunk) == 0:
                continue
            scaler.partial_fit(chunk)
            seen = True
    if not seen:
        raise ValueError("No data supplied to scaler")

    scale = scaler.scale_.astype(np.float32)
    scale[~np.isfinite(scale) | (scale == 0)] = 1.0
    return scaler.mean_.astype(np.float32), scale


def apply_scaler(
    array: np.ndarray, mean: np.ndarray, scale: np.ndarray
) -> np.ndarray:
    array -= mean
    array /= scale
    return array


def balanced_class_weights(
    y: np.ndarray, num_classes: int
) -> np.ndarray:
    counts = np.bincount(y, minlength=num_classes).astype(np.float64)
    counts[counts == 0] = 1.0
    weights = counts.sum() / (num_classes * counts)
    return weights.astype(np.float32)


def prepare_federated_data(
    train_csv: str | Path,
    partitions: Sequence[np.ndarray],
    classes: Sequence[str] | None = None,
    feature_columns: Sequence[str] | None = None,
    max_samples_per_client: int | None = None,
    validation_fraction: float = 0.1,
    seed: int = 42,
    verbose: bool = True,
) -> FederatedData:
    """End-to-end preparation used by the experiment runner and tests."""

    X, y, loaded_classes, features = load_training_data(
        train_csv, feature_columns=feature_columns
    )
    if classes is not None and list(classes) != loaded_classes:
        raise ValueError("Supplied class list does not match training labels")

    clients, client_meta = build_clients(
        X, y, partitions, max_samples_per_client=max_samples_per_client, seed=seed
    )
    del X

    train_clients, val_X, val_y, split_meta = split_validation(
        clients, validation_fraction=validation_fraction, seed=seed
    )
    del clients

    mean, scale = fit_scaler(client.X for client in train_clients)

    for client in train_clients:
        apply_scaler(client.X, mean, scale)
    if len(val_X):
        apply_scaler(val_X, mean, scale)

    metadata = {
        "train_csv": str(Path(train_csv)),
        "num_clients": len(train_clients),
        "classes": loaded_classes,
        "feature_names": features,
        "max_samples_per_client": max_samples_per_client,
        "validation_fraction": validation_fraction,
        "seed": seed,
        "client_sampling": client_meta,
        "validation_split": split_meta,
        "train_records_total": int(sum(c.n_samples for c in train_clients)),
        "validation_records_total": int(len(val_y)),
        "preprocessing_fit_on": "client training subsets only",
        "test_split_used": False,
    }

    return FederatedData(
        clients=train_clients,
        val_X=val_X,
        val_y=val_y,
        classes=list(loaded_classes),
        feature_names=features,
        scaler_mean=mean,
        scaler_scale=scale,
        metadata=metadata,
    )
