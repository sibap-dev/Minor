"""Client context model and context generation.

Every contextual field records its provenance.  Generated profiles are
explicitly ``simulated``; they must never be presented as hardware
measurements from independent physical devices.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np

FIELDS = [
    "cpu_percent",
    "memory_percent",
    "memory_available_mb",
    "disk_percent",
    "latency_ms",
    "packet_loss_percent",
    "bandwidth_mbps",
    "jitter_ms",
    "availability",
]

VALID_PROVENANCE = {"measured", "simulated", "estimated", "unavailable"}


@dataclass
class ClientContext:
    client_id: str
    cpu_percent: float | None = None
    memory_percent: float | None = None
    memory_available_mb: float | None = None
    disk_percent: float | None = None
    latency_ms: float | None = None
    packet_loss_percent: float | None = None
    bandwidth_mbps: float | None = None
    jitter_ms: float | None = None
    availability: float | None = None
    local_samples: int = 0
    class_coverage: int = 0
    total_classes: int = 0
    rounds_since_selected: int = 0
    enabled: bool = True
    provenance: dict[str, str] = field(default_factory=dict)
    notes: str = ""

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not self.client_id:
            raise ValueError("client_id is required")
        if self.local_samples < 0:
            raise ValueError(f"local_samples must be >= 0 for {self.client_id}")
        if self.class_coverage < 0:
            raise ValueError(f"class_coverage must be >= 0 for {self.client_id}")
        if self.total_classes < 0:
            raise ValueError(f"total_classes must be >= 0 for {self.client_id}")
        if self.class_coverage > self.total_classes and self.total_classes > 0:
            raise ValueError(
                f"class_coverage cannot exceed total_classes for {self.client_id}"
            )

        ranges = {
            "cpu_percent": (0.0, 100.0),
            "memory_percent": (0.0, 100.0),
            "memory_available_mb": (0.0, None),
            "disk_percent": (0.0, 100.0),
            "latency_ms": (0.0, None),
            "packet_loss_percent": (0.0, 100.0),
            "bandwidth_mbps": (0.0, None),
            "jitter_ms": (0.0, None),
            "availability": (0.0, 1.0),
        }
        for name, (low, high) in ranges.items():
            value = getattr(self, name)
            if value is None:
                self.provenance.setdefault(name, "unavailable")
                continue
            if not np.isfinite(value):
                raise ValueError(f"{name} must be finite for {self.client_id}")
            if value < low or (high is not None and value > high):
                raise ValueError(
                    f"{name}={value} outside [{low}, {high}] for {self.client_id}"
                )
            self.provenance.setdefault(name, "estimated")

        for name in FIELDS:
            source = self.provenance.get(name, "unavailable")
            if source not in VALID_PROVENANCE:
                raise ValueError(
                    f"Invalid provenance '{source}' for {name} on {self.client_id}"
                )

        if self.provenance and any(
            source == "measured" for source in self.provenance.values()
        ):
            self.notes = self.notes or "contains measured fields"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ClientContext":
        known = {field_name for field_name in cls.__dataclass_fields__}
        unknown = set(payload) - known
        if unknown:
            raise ValueError(f"Unknown context fields: {sorted(unknown)}")
        return cls(**payload)

    def available(self) -> dict[str, float]:
        return {
            name: float(getattr(self, name))
            for name in FIELDS
            if getattr(self, name) is not None
        }


def load_context_file(path: str | Path) -> tuple[list[ClientContext], dict]:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Context file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    clients_payload = payload.get("clients", payload)
    if isinstance(clients_payload, dict):
        clients_payload = list(clients_payload.values())
    clients = [ClientContext.from_dict(item) for item in clients_payload]
    return clients, payload.get("metadata", {})


def _default_profiles() -> list[dict[str, Any]]:
    """Five interpretable heterogeneous IoT-like profiles."""

    return [
        {
            "name": "edge-gateway-strong",
            "cpu_percent": 25.0,
            "memory_percent": 42.0,
            "memory_available_mb": 4096.0,
            "disk_percent": 55.0,
            "latency_ms": 22.0,
            "packet_loss_percent": 0.4,
            "bandwidth_mbps": 90.0,
            "jitter_ms": 3.0,
            "availability": 0.98,
        },
        {
            "name": "sensor-hub-moderate",
            "cpu_percent": 55.0,
            "memory_percent": 64.0,
            "memory_available_mb": 1536.0,
            "disk_percent": 68.0,
            "latency_ms": 65.0,
            "packet_loss_percent": 2.5,
            "bandwidth_mbps": 35.0,
            "jitter_ms": 9.0,
            "availability": 0.90,
        },
        {
            "name": "constrained-camera",
            "cpu_percent": 86.0,
            "memory_percent": 81.0,
            "memory_available_mb": 384.0,
            "disk_percent": 88.0,
            "latency_ms": 145.0,
            "packet_loss_percent": 7.5,
            "bandwidth_mbps": 12.0,
            "jitter_ms": 22.0,
            "availability": 0.70,
        },
        {
            "name": "lan-node-low-load",
            "cpu_percent": 30.0,
            "memory_percent": 48.0,
            "memory_available_mb": 3072.0,
            "disk_percent": 45.0,
            "latency_ms": 38.0,
            "packet_loss_percent": 1.0,
            "bandwidth_mbps": 70.0,
            "jitter_ms": 5.0,
            "availability": 0.95,
        },
        {
            "name": "remote-node-weak-network",
            "cpu_percent": 62.0,
            "memory_percent": 72.0,
            "memory_available_mb": 1024.0,
            "disk_percent": 74.0,
            "latency_ms": 310.0,
            "packet_loss_percent": 14.0,
            "bandwidth_mbps": 5.0,
            "jitter_ms": 48.0,
            "availability": 0.62,
        },
    ]


def generate_simulated_context(
    partition_report: dict,
    seed: int = 42,
    jitter: bool = True,
) -> tuple[list[ClientContext], dict]:
    """Create deterministic simulated client-context profiles.

    Local sample counts and class coverage come from the real partition
    report.  Resource and network values are simulated and labelled as such.
    """

    rng = np.random.default_rng(seed)
    profiles = _default_profiles()
    client_items = list(partition_report["clients"].items())
    total_classes = int(partition_report.get("number_of_classes", 34))
    if not total_classes:
        total_classes = max(
            len(details.get("class_distribution", {}))
            for _, details in client_items
        )

    clients: list[ClientContext] = []
    for index, (client_name, details) in enumerate(client_items):
        profile = dict(profiles[index % len(profiles)])
        profile.pop("name", None)

        if jitter:
            for name in (
                "cpu_percent",
                "memory_percent",
                "memory_available_mb",
                "latency_ms",
                "packet_loss_percent",
                "bandwidth_mbps",
                "jitter_ms",
                "availability",
            ):
                scale = {
                    "cpu_percent": 4.0,
                    "memory_percent": 3.0,
                    "memory_available_mb": 0.08,
                    "latency_ms": 0.10,
                    "packet_loss_percent": 0.20,
                    "bandwidth_mbps": 0.08,
                    "jitter_ms": 0.15,
                    "availability": 0.02,
                }[name]
                noise = rng.normal(0.0, scale * abs(profile[name]) if name != "availability" else scale)
                profile[name] = float(profile[name] + noise)

            profile["cpu_percent"] = float(np.clip(profile["cpu_percent"], 0, 100))
            profile["memory_percent"] = float(np.clip(profile["memory_percent"], 0, 100))
            profile["memory_available_mb"] = max(64.0, profile["memory_available_mb"])
            profile["latency_ms"] = max(1.0, profile["latency_ms"])
            profile["packet_loss_percent"] = float(
                np.clip(profile["packet_loss_percent"], 0, 100)
            )
            profile["bandwidth_mbps"] = max(0.5, profile["bandwidth_mbps"])
            profile["jitter_ms"] = max(0.0, profile["jitter_ms"])
            profile["availability"] = float(np.clip(profile["availability"], 0, 1))

        provenance = {name: "simulated" for name in FIELDS}
        provenance["local_samples"] = "measured"
        provenance["class_coverage"] = "measured"

        clients.append(
            ClientContext(
                client_id=client_name,
                local_samples=int(details["records"]),
                class_coverage=int(details.get("class_count", 0)),
                total_classes=total_classes,
                provenance=provenance,
                **profile,
            )
        )

    metadata = {
        "provenance": "simulated",
        "seed": seed,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Resource and network values are simulated profiles for logical "
            "clients on shared hardware. They are not independent physical "
            "measurements. local_samples and class_coverage are derived from "
            "the real partition report."
        ),
    }
    return clients, metadata


def write_context_file(
    path: str | Path,
    clients: Iterable[ClientContext],
    metadata: dict,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": metadata,
        "clients": [client.to_dict() for client in clients],
    }
    path.write_text(json.dumps(payload, indent=4), encoding="utf-8")
    return path
