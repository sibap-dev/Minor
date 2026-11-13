"""Context-aware client selection.

The method is deliberately modular and explainable:

1. Validate incoming context.
2. Apply hard eligibility constraints.
3. Normalise each criterion across candidates (min-max, missing -> neutral).
4. Combine criteria into category scores with explicit weights.
5. Rank and select ``k`` clients with deterministic tie-breaking.
6. Record per-client scores, contributions and rejection reasons.

Three comparison strategies are provided: random, resource-aware and the
proposed context-aware method.  A conventional "all clients" baseline is also
provided for FedAvg full participation.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Sequence

import numpy as np

from .context import ClientContext


DEFAULT_WEIGHTS = {
    "resource": 0.30,
    "network": 0.20,
    "data": 0.25,
    "fairness": 0.15,
    "cost": 0.10,
}

RESOURCE_AWARE_WEIGHTS = {
    "resource": 0.70,
    "cost": 0.30,
}


@dataclass(frozen=True)
class SelectionConfig:
    num_select: int = 3
    min_availability: float = 0.50
    max_cpu_percent: float = 95.0
    min_memory_available_mb: float = 128.0
    max_disk_percent: float = 98.0
    max_latency_ms: float = 1000.0
    max_packet_loss_percent: float = 50.0
    weights: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_WEIGHTS)
    )

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if self.num_select < 1:
            raise ValueError("num_select must be >= 1")
        missing = {"resource", "network", "data", "fairness", "cost"} - set(
            self.weights
        )
        if missing:
            raise ValueError(f"Missing weights: {sorted(missing)}")
        if any(weight < 0 for weight in self.weights.values()):
            raise ValueError("Weights must be non-negative")
        if self.weights["cost"] > 1.0:
            raise ValueError("cost weight must be <= 1")


@dataclass
class ClientScore:
    client_id: str
    eligible: bool
    eligibility_reasons: list[str]
    missing_metrics: list[str]
    score: float
    contributions: dict[str, float]
    cost_proxy: float
    selected: bool = False
    selection_rank: int | None = None
    decision_reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SelectionResult:
    strategy: str
    round_number: int
    requested: int
    selected: list[str]
    scores: dict[str, ClientScore]
    constraints_relaxed: bool
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy,
            "round_number": self.round_number,
            "requested": self.requested,
            "selected": self.selected,
            "constraints_relaxed": self.constraints_relaxed,
            "notes": self.notes,
            "clients": {
                name: score.to_dict() for name, score in self.scores.items()
            },
        }


def _normalise(
    values: dict[str, float | None], higher_is_better: bool
) -> dict[str, float]:
    """Min-max normalise to [0, 1]; missing values -> 0.5.

    If there is no spread, every candidate receives 0.5.  This makes the score
    invariant to absolute metric units and avoids division by zero.
    """

    present = [value for value in values.values() if value is not None]
    if len(present) < 1:
        return {name: 0.5 for name in values}

    low = min(present)
    high = max(present)
    if high == low:
        return {name: 0.5 for name in values}

    result = {}
    for name, value in values.items():
        if value is None:
            result[name] = 0.5
        else:
            scaled = (value - low) / (high - low)
            result[name] = float(scaled if higher_is_better else 1.0 - scaled)
    return result


def _mean(parts: Sequence[float]) -> float:
    return float(np.mean(parts)) if parts else 0.5


def _eligibility(
    client: ClientContext, config: SelectionConfig
) -> tuple[bool, list[str], list[str]]:
    reasons: list[str] = []
    missing: list[str] = []

    if not client.enabled:
        reasons.append("client_disabled")

    checks = [
        ("availability", config.min_availability, "min"),
        ("cpu_percent", config.max_cpu_percent, "max"),
        ("memory_available_mb", config.min_memory_available_mb, "min"),
        ("disk_percent", config.max_disk_percent, "max"),
        ("latency_ms", config.max_latency_ms, "max"),
        ("packet_loss_percent", config.max_packet_loss_percent, "max"),
    ]

    for name, threshold, direction in checks:
        value = getattr(client, name)
        if value is None:
            missing.append(name)
            continue
        if direction == "min" and value < threshold:
            reasons.append(f"{name}_below_{threshold:g}")
        if direction == "max" and value > threshold:
            reasons.append(f"{name}_above_{threshold:g}")

    return len(reasons) == 0, reasons, missing


def _cost_proxy(client: ClientContext) -> float:
    """Estimated relative training/communication cost.

    This is an explicitly labelled proxy, not measured energy.  It increases
    with local dataset size and CPU load and decreases with bandwidth.
    """

    cpu = float(client.cpu_percent) if client.cpu_percent is not None else 50.0
    bandwidth = (
        float(client.bandwidth_mbps)
        if client.bandwidth_mbps is not None
        else 1.0
    )
    bandwidth = max(bandwidth, 0.5)
    return float(
        np.log1p((client.local_samples * (0.25 + cpu / 100.0)) / bandwidth)
    )


def score_clients(
    clients: Sequence[ClientContext],
    config: SelectionConfig,
    strategy: str,
) -> tuple[dict[str, ClientScore], bool, list[str]]:
    """Compute scores for one strategy.  Shared normalisation across clients."""

    if strategy not in {"resource", "context"}:
        raise ValueError(f"Scoring not defined for strategy '{strategy}'")

    config.validate()
    by_id = {client.client_id: client for client in clients}
    if len(by_id) != len(clients):
        raise ValueError("Duplicate client identifiers in context")

    eligibility = {
        client.client_id: _eligibility(client, config) for client in clients
    }

    def values(name: str) -> dict[str, float | None]:
        return {client.client_id: getattr(client, name) for client in clients}

    cpu_headroom = {
        client_id: (100.0 - value) if value is not None else None
        for client_id, value in values("cpu_percent").items()
    }
    memory_headroom = {
        client_id: (100.0 - value) if value is not None else None
        for client_id, value in values("memory_percent").items()
    }

    cpu_n = _normalise(cpu_headroom, higher_is_better=True)
    mem_n = _normalise(memory_headroom, higher_is_better=True)
    mem_abs_n = _normalise(values("memory_available_mb"), higher_is_better=True)
    avail_n = _normalise(values("availability"), higher_is_better=True)

    latency_n = _normalise(values("latency_ms"), higher_is_better=False)
    loss_n = _normalise(values("packet_loss_percent"), higher_is_better=False)
    bw_n = _normalise(values("bandwidth_mbps"), higher_is_better=True)
    jitter_n = _normalise(values("jitter_ms"), higher_is_better=False)

    log_samples = {
        client_id: np.log1p(float(client.local_samples))
        for client_id, client in by_id.items()
    }
    data_n = _normalise(log_samples, higher_is_better=True)
    coverage = {
        client_id: (
            client.class_coverage / client.total_classes
            if client.total_classes > 0
            else None
        )
        for client_id, client in by_id.items()
    }
    coverage_n = _normalise(coverage, higher_is_better=True)

    max_rounds = max(
        (client.rounds_since_selected for client in clients), default=0
    )
    fairness_raw = {
        client.client_id: (
            client.rounds_since_selected / max_rounds if max_rounds > 0 else None
        )
        for client in clients
    }
    fairness_n = _normalise(fairness_raw, higher_is_better=True)

    cost_values = {client.client_id: _cost_proxy(client) for client in clients}
    cost_n = _normalise(cost_values, higher_is_better=False)

    scores: dict[str, ClientScore] = {}
    for client in clients:
        cid = client.client_id
        eligible, reasons, missing = eligibility[cid]

        memory_score = _mean(
            [m for m in (mem_n[cid], mem_abs_n[cid])]
        )
        resource_score = 0.5 * cpu_n[cid] + 0.5 * memory_score
        network_score = (
            0.45 * latency_n[cid]
            + 0.30 * loss_n[cid]
            + 0.15 * bw_n[cid]
            + 0.10 * jitter_n[cid]
        )
        data_score = 0.60 * data_n[cid] + 0.40 * coverage_n[cid]
        fairness_score = fairness_n[cid]
        cost_score = cost_n[cid]  # higher means more expensive

        if strategy == "resource":
            w = RESOURCE_AWARE_WEIGHTS
            score = (
                w["resource"] * resource_score
                + w["cost"] * (1.0 - cost_score)
            )
            contributions = {
                "resource": w["resource"] * resource_score,
                "cost_avoidance": w["cost"] * (1.0 - cost_score),
            }
        else:
            w = config.weights
            score = (
                w["resource"] * resource_score
                + w["network"] * network_score
                + w["data"] * data_score
                + w["fairness"] * fairness_score
                - w["cost"] * cost_score
            )
            contributions = {
                "resource": w["resource"] * resource_score,
                "network": w["network"] * network_score,
                "data": w["data"] * data_score,
                "fairness": w["fairness"] * fairness_score,
                "cost_penalty": -w["cost"] * cost_score,
            }

        scores[cid] = ClientScore(
            client_id=cid,
            eligible=eligible,
            eligibility_reasons=reasons,
            missing_metrics=missing,
            score=float(score),
            contributions={name: float(value) for name, value in contributions.items()},
            cost_proxy=float(cost_values[cid]),
        )

    return scores, False, []


def _rank(
    scores: dict[str, ClientScore], num_select: int
) -> tuple[list[str], bool, list[str]]:
    notes: list[str] = []
    eligible_ids = [
        cid for cid, score in scores.items() if score.eligible
    ]
    eligible_ids.sort(key=lambda cid: (-scores[cid].score, cid))

    selected = eligible_ids[:num_select]
    relaxed = False

    if len(selected) < num_select:
        relaxed = True
        ineligible_ids = [
            cid for cid, score in scores.items() if not score.eligible
        ]
        ineligible_ids.sort(key=lambda cid: (-scores[cid].score, cid))
        needed = num_select - len(selected)
        selected.extend(ineligible_ids[:needed])
        notes.append(
            f"Only {len(eligible_ids)} eligible clients; relaxed constraints "
            f"for {len(ineligible_ids[:needed])} additional client(s)."
        )

    for rank, cid in enumerate(selected, start=1):
        score = scores[cid]
        score.selected = True
        score.selection_rank = rank
        if score.eligible:
            score.decision_reason = "selected_eligible_highest_score"
        else:
            score.decision_reason = "selected_constraint_relaxed"

    for cid, score in scores.items():
        if score.selected:
            continue
        if not score.eligible:
            score.decision_reason = "not_eligible:" + ",".join(
                score.eligibility_reasons
            )
        else:
            score.decision_reason = "not_selected_lower_score"

    return selected, relaxed, notes


def _random_selection(
    clients: Sequence[ClientContext], num_select: int, seed: int, round_number: int
) -> SelectionResult:
    enabled = [client for client in clients if client.enabled]
    if not enabled:
        raise ValueError("No enabled clients available for selection")
    rng = np.random.default_rng(seed + round_number)
    available_ids = [client.client_id for client in enabled]
    chosen = rng.choice(
        available_ids, size=min(num_select, len(available_ids)), replace=False
    )
    selected = [str(client_id) for client_id in chosen]
    scores = {}
    for client in clients:
        eligible = client.enabled
        scores[client.client_id] = ClientScore(
            client_id=client.client_id,
            eligible=eligible,
            eligibility_reasons=[] if eligible else ["client_disabled"],
            missing_metrics=[
                name for name in client.__dataclass_fields__ if getattr(client, name) is None
            ],
            score=1.0 if client.client_id in selected else 0.0,
            contributions={},
            cost_proxy=_cost_proxy(client),
            selected=client.client_id in selected,
            selection_rank=(
                selected.index(client.client_id) + 1
                if client.client_id in selected
                else None
            ),
            decision_reason=(
                "selected_uniform_random"
                if client.client_id in selected
                else "not_selected_random_draw"
            ),
        )
    return SelectionResult(
        strategy="random",
        round_number=round_number,
        requested=num_select,
        selected=selected,
        scores=scores,
        constraints_relaxed=False,
        notes=["Uniform random selection without replacement."],
    )


def select_clients(
    clients: Sequence[ClientContext],
    strategy: str,
    config: SelectionConfig,
    seed: int = 42,
    round_number: int = 0,
) -> SelectionResult:
    """Entry point for all selection strategies.

    Strategies: ``all`` (full participation), ``random``, ``resource``,
    ``context``.
    """

    config.validate()
    if not clients:
        raise ValueError("No clients supplied")
    if len({client.client_id for client in clients}) != len(clients):
        raise ValueError("Duplicate client identifiers")

    if strategy == "all":
        enabled = [client for client in clients if client.enabled]
        if not enabled:
            raise ValueError("No enabled clients available")
        selected = [client.client_id for client in enabled]
        scores = {
            client.client_id: ClientScore(
                client_id=client.client_id,
                eligible=True,
                eligibility_reasons=[] if client.enabled else ["client_disabled"],
                missing_metrics=[],
                score=1.0,
                contributions={},
                cost_proxy=_cost_proxy(client),
                selected=client.enabled,
                selection_rank=(
                    selected.index(client.client_id) + 1 if client.enabled else None
                ),
                decision_reason=(
                    "selected_full_participation"
                    if client.enabled
                    else "not_selected_disabled"
                ),
            )
            for client in clients
        }
        return SelectionResult(
            strategy="all",
            round_number=round_number,
            requested=len(clients),
            selected=selected,
            scores=scores,
            constraints_relaxed=False,
            notes=["Conventional FedAvg full participation."],
        )

    if strategy == "random":
        return _random_selection(clients, config.num_select, seed, round_number)

    if strategy not in {"resource", "context"}:
        raise ValueError(
            f"Unknown strategy '{strategy}'. Use all|random|resource|context."
        )

    scores, _, _ = score_clients(clients, config, strategy)
    selected, relaxed, notes = _rank(scores, config.num_select)
    return SelectionResult(
        strategy=strategy,
        round_number=round_number,
        requested=config.num_select,
        selected=selected,
        scores=scores,
        constraints_relaxed=relaxed,
        notes=notes,
    )


def update_participation(
    clients: Sequence[ClientContext], selected: Sequence[str]
) -> None:
    """Update fairness counters in place after a training round."""

    selected_set = set(selected)
    for client in clients:
        if client.client_id in selected_set:
            client.rounds_since_selected = 0
        else:
            client.rounds_since_selected += 1
