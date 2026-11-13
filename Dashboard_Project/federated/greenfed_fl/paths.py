"""Filesystem path resolution with environment overrides.

The repository has data at the parent level and the monitoring application in
a nested folder.  Defaults resolve both layouts so scripts can run from the
repository root regardless of the current working directory.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = REPO_ROOT / "GreenFed-IDS-main" / "GreenFed-IDS-main"
FEDERATED_ROOT = REPO_ROOT / "federated"

TRAIN_CSV = Path(os.environ.get("GREENFED_TRAIN_CSV", REPO_ROOT / "output" / "splits" / "train.csv"))
TEST_CSV = Path(os.environ.get("GREENFED_TEST_CSV", REPO_ROOT / "output" / "splits" / "test.csv"))
PARTITIONS_DIR = Path(
    os.environ.get("GREENFED_PARTITIONS_DIR", APP_ROOT / "output" / "partitions")
)
RESULTS_DIR = Path(os.environ.get("GREENFED_RESULTS_DIR", FEDERATED_ROOT / "results"))
CONTEXT_DIR = Path(os.environ.get("GREENFED_CONTEXT_DIR", FEDERATED_ROOT / "context"))

LABEL_COLUMN = "Label"


def ensure_dirs(*paths: Path) -> None:
    for path in paths:
        Path(path).mkdir(parents=True, exist_ok=True)


def partition_dir(method: str) -> Path:
    return PARTITIONS_DIR / method


def require_file(path: Path, description: str) -> Path:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"{description} not found: {path}")
    return path
