import copy

import numpy as np
import pytest

from greenfed_fl.context import ClientContext
from greenfed_fl.selection import (
    SelectionConfig,
    select_clients,
    update_participation,
)


def make_client(cid, **overrides):
    payload = {
        "client_id": cid,
        "cpu_percent": 30.0,
        "memory_percent": 40.0,
        "memory_available_mb": 2048.0,
        "disk_percent": 50.0,
        "latency_ms": 30.0,
        "packet_loss_percent": 1.0,
        "bandwidth_mbps": 80.0,
        "jitter_ms": 4.0,
        "availability": 0.95,
        "local_samples": 1000,
        "class_coverage": 34,
        "total_classes": 34,
        "provenance": {name: "simulated" for name in [
            "cpu_percent", "memory_percent", "memory_available_mb",
            "disk_percent", "latency_ms", "packet_loss_percent",
            "bandwidth_mbps", "jitter_ms", "availability",
        ]},
    }
    payload.update(overrides)
    return ClientContext(**payload)


def base_clients():
    return [make_client(f"client_{i}") for i in range(1, 6)]


def test_all_strategy_selects_every_enabled_client():
    clients = base_clients()
    clients[4].enabled = False
    result = select_clients(clients, "all", SelectionConfig(num_select=3))
    assert result.selected == ["client_1", "client_2", "client_3", "client_4"]
    assert result.scores["client_5"].selected is False


def test_random_is_reproducible_for_same_seed_and_round():
    clients = base_clients()
    config = SelectionConfig(num_select=3)
    first = select_clients(clients, "random", config, seed=5, round_number=1)
    second = select_clients(clients, "random", config, seed=5, round_number=1)
    assert first.selected == second.selected
    assert len(first.selected) == 3


def test_random_changes_across_rounds():
    clients = base_clients()
    config = SelectionConfig(num_select=3)
    draws = {
        tuple(select_clients(clients, "random", config, seed=5, round_number=r).selected)
        for r in range(1, 6)
    }
    assert len(draws) > 1


def test_eligibility_filters_overloaded_client():
    clients = base_clients()
    clients[2].cpu_percent = 99.0
    result = select_clients(
        clients, "context", SelectionConfig(num_select=3)
    )
    score = result.scores["client_3"]
    assert score.eligible is False
    assert any("cpu_percent_above" in reason for reason in score.eligibility_reasons)
    assert "client_3" not in result.selected


def test_constraint_relaxation_when_too_few_eligible():
    clients = base_clients()
    for client in clients[:4]:
        client.cpu_percent = 99.0
    result = select_clients(clients, "context", SelectionConfig(num_select=3))
    assert result.constraints_relaxed is True
    assert len(result.selected) == 3
    assert any(
        result.scores[cid].decision_reason.startswith("selected_constraint_relaxed")
        for cid in result.selected
    )


def test_missing_metrics_are_handled_without_crashing():
    clients = base_clients()
    clients[0].latency_ms = None
    clients[0].packet_loss_percent = None
    clients[1].memory_available_mb = None
    result = select_clients(clients, "context", SelectionConfig(num_select=2))
    assert len(result.selected) == 2
    assert "latency_ms" in result.scores["client_1"].missing_metrics


def test_resource_aware_ignores_network_differences_but_context_does_not():
    resource_a = make_client("client_1")
    resource_b = make_client(
        "client_2", latency_ms=300.0, packet_loss_percent=20.0
    )
    clients = [resource_a, resource_b]

    resource_result = select_clients(
        clients, "resource", SelectionConfig(num_select=1)
    )
    resource_scores = [
        resource_result.scores[cid].score for cid in ("client_1", "client_2")
    ]
    assert resource_scores[0] == pytest.approx(resource_scores[1], abs=1e-9)

    context_result = select_clients(
        clients, "context", SelectionConfig(num_select=1)
    )
    assert context_result.scores["client_1"].score > context_result.scores["client_2"].score


def test_fairness_bonus_favours_long_unselected_client():
    clients = [make_client(f"client_{i}") for i in range(1, 6)]
    clients[4].rounds_since_selected = 10
    result = select_clients(clients, "context", SelectionConfig(num_select=3))
    assert "client_5" in result.selected
    assert result.scores["client_5"].contributions["fairness"] > 0


def test_scores_have_explanations_for_selected_and_unselected():
    clients = base_clients()
    result = select_clients(clients, "context", SelectionConfig(num_select=2))
    for cid, score in result.scores.items():
        assert score.decision_reason
        assert "resource" in score.contributions
    assert sum(score.selected for score in result.scores.values()) == 2


def test_setting_validation_rejects_bad_weights():
    with pytest.raises(ValueError):
        SelectionConfig(num_select=2, weights={"resource": 1.0})


def test_duplicate_client_ids_rejected():
    clients = [make_client("dup"), make_client("dup")]
    with pytest.raises(ValueError):
        select_clients(clients, "context", SelectionConfig(num_select=1))


def test_unknown_strategy_rejected():
    with pytest.raises(ValueError):
        select_clients(base_clients(), "magic", SelectionConfig(num_select=1))


def test_participation_counters_update():
    clients = base_clients()
    update_participation(clients, ["client_1", "client_3"])
    assert clients[0].rounds_since_selected == 0
    assert clients[1].rounds_since_selected == 1
    assert clients[2].rounds_since_selected == 0
