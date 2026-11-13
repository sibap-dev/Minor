"""Run reproducible FedAvg experiments with different selection strategies.

Example (reduced smoke run):
    python federated/run_experiment.py --scenario iid --strategy all \
        --rounds 1 --max-samples-per-client 20000

Full comparison:
    python federated/run_experiment.py --scenario non_iid \
        --strategy all --strategies-all --rounds 2
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from greenfed_fl.context import (
    ClientContext,
    generate_simulated_context,
    load_context_file,
)
from greenfed_fl.data import (
    apply_scaler,
    load_test_data,
    prepare_federated_data,
)
from greenfed_fl.fedavg import TrainConfig, run_federated_experiment
from greenfed_fl.partitioning import load_partition_report, read_partition_indices
from greenfed_fl.paths import (
    CONTEXT_DIR,
    PARTITIONS_DIR,
    RESULTS_DIR,
    TEST_CSV,
    TRAIN_CSV,
)
from greenfed_fl.selection import (
    ClientScore,
    SelectionConfig,
    SelectionResult,
    select_clients,
)

STRATEGIES = ["all", "random", "resource", "context"]


def json_default(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value)} is not JSON serializable")


def write_rounds_csv(results: dict, path: Path) -> None:
    rows = []
    for round_data in results["rounds"]:
        validation = round_data["validation"]
        row = {
            "strategy": results["strategy"],
            "scenario": results["scenario"],
            "round": round_data["round"],
            "selected_clients": "|".join(round_data["selected_clients"]),
            "constraints_relaxed": round_data["selection"]["constraints_relaxed"],
            "accuracy": validation.get("accuracy"),
            "balanced_accuracy": validation.get("balanced_accuracy"),
            "macro_f1": validation.get("macro_f1"),
            "weighted_f1": validation.get("weighted_f1"),
            "communication_bytes_round": round_data["communication_bytes_round"],
            "cpu_seconds_round": round_data["cpu_seconds_round"],
            "training_seconds_round": round_data["training_seconds_round"],
            "wall_seconds_round": round_data["wall_seconds_round"],
        }
        rows.append(row)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def fresh_contexts(base: list[ClientContext]) -> list[ClientContext]:
    return [ClientContext.from_dict(item.to_dict()) for item in base]


def load_selection_override(path: Path) -> SelectionResult:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    scores = {}
    for client_id, item in payload.get("clients", {}).items():
        allowed = {
            key: value
            for key, value in item.items()
            if key in ClientScore.__dataclass_fields__
        }
        scores[client_id] = ClientScore(**allowed)
    return SelectionResult(
        strategy=payload["strategy"],
        round_number=int(payload.get("round_number", 0)),
        requested=int(payload.get("requested", len(payload.get("selected", [])))),
        selected=list(payload.get("selected", [])),
        scores=scores,
        constraints_relaxed=bool(payload.get("constraints_relaxed", False)),
        notes=list(payload.get("notes", [])),
    )


def summary_row(results: dict) -> dict:
    test = results.get("test") or {}
    validation = results.get("final_validation") or {}
    resources = results["resource_summary"]
    return {
        "scenario": results["scenario"],
        "strategy": results["strategy"],
        "rounds": results["configuration"]["rounds"],
        "num_select": (
            results["configuration"].get("participants_per_round", [None])[0]
        ),
        "validation_accuracy": validation.get("accuracy"),
        "validation_balanced_accuracy": validation.get("balanced_accuracy"),
        "validation_macro_f1": validation.get("macro_f1"),
        "test_accuracy": test.get("accuracy"),
        "test_balanced_accuracy": test.get("balanced_accuracy"),
        "test_macro_f1": test.get("macro_f1"),
        "test_weighted_f1": test.get("weighted_f1"),
        "communication_megabytes_total": resources["communication_megabytes_total"],
        "cpu_seconds_total": resources["cpu_seconds_total"],
        "training_seconds_total": resources["training_seconds_total"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default="iid", choices=["iid", "non_iid"])
    parser.add_argument(
        "--strategy",
        default="context",
        choices=STRATEGIES + ["all-strategies"],
        help="Selection strategy, or 'all-strategies' for the full comparison",
    )
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--local-epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--num-select", type=int, default=3)
    parser.add_argument("--validation-fraction", type=float, default=0.1)
    parser.add_argument(
        "--max-samples-per-client",
        type=int,
        default=None,
        help="Deterministic per-client subsample for reduced-scale runs",
    )
    parser.add_argument("--class-weight-mode", default="none", choices=["none", "balanced"])
    parser.add_argument("--num-threads", type=int, default=4)
    parser.add_argument("--context-file", type=Path, default=None)
    parser.add_argument("--context-seed", type=int, default=42)
    parser.add_argument("--train-csv", type=Path, default=TRAIN_CSV)
    parser.add_argument("--test-csv", type=Path, default=TEST_CSV)
    parser.add_argument("--partitions-dir", type=Path, default=PARTITIONS_DIR)
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--tag", default="")
    parser.add_argument("--run-id", default=None)
    parser.add_argument(
        "--selection-file",
        type=Path,
        default=None,
        help="Dashboard selection JSON; fixes the exact clients for every round",
    )
    parser.add_argument("--no-test-eval", action="store_true")
    args = parser.parse_args()

    strategies = (
        STRATEGIES if args.strategy == "all-strategies" else [args.strategy]
    )
    selection_override = None
    if args.selection_file is not None:
        if args.strategy == "all-strategies":
            raise ValueError(
                "--selection-file cannot be combined with --strategy all-strategies"
            )
        selection_override = load_selection_override(args.selection_file)
        if selection_override.strategy != args.strategy:
            raise ValueError(
                f"Selection strategy '{selection_override.strategy}' does not "
                f"match training strategy '{args.strategy}'"
            )
        strategies = [selection_override.strategy]

    start = time.perf_counter()
    if args.run_id:
        if Path(args.run_id).name != args.run_id:
            raise ValueError("--run-id must be a directory name, not a path")
        run_id = args.run_id
    else:
        run_id = (
            datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            + f"_{args.scenario}_s{args.seed}"
            + (f"_{args.tag}" if args.tag else "")
        )
    run_dir = args.output_dir / run_id
    if run_dir.exists() and any(run_dir.iterdir()):
        raise FileExistsError(f"Run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"Run directory: {run_dir}")

    partition_dir = args.partitions_dir / args.scenario
    partitions = read_partition_indices(partition_dir)
    report = load_partition_report(partition_dir)
    print(
        f"Loaded {len(partitions)} partitions from {partition_dir} "
        f"(seed={report.get('random_seed')}, alpha={report.get('dirichlet_alpha')})"
    )

    if args.context_file:
        base_contexts, context_meta = load_context_file(args.context_file)
        print(f"Loaded context from {args.context_file}")
    else:
        base_contexts, context_meta = generate_simulated_context(
            report, seed=args.context_seed, jitter=True
        )
        context_path = CONTEXT_DIR / (
            f"{args.scenario}_context_seed{args.context_seed}.json"
        )
        from greenfed_fl.context import write_context_file

        write_context_file(context_path, base_contexts, context_meta)
        print(f"Generated simulated context: {context_path}")

    if selection_override is not None:
        context_ids = {client.client_id for client in base_contexts}
        unknown = set(selection_override.selected) - context_ids
        if unknown:
            raise ValueError(
                f"Selection references unknown clients: {sorted(unknown)}"
            )
        shutil.copyfile(args.selection_file, run_dir / "selection_input.json")
        print(
            f"Using fixed dashboard selection: {selection_override.selected} "
            f"(relaxed={selection_override.constraints_relaxed})"
        )

    print("Preparing federated data (training split only)...")
    data = prepare_federated_data(
        args.train_csv,
        partitions,
        max_samples_per_client=args.max_samples_per_client,
        validation_fraction=args.validation_fraction,
        seed=args.seed,
        verbose=True,
    )
    print(
        f"Clients: {[c.n_samples for c in data.clients]} | "
        f"validation rows: {len(data.val_y):,}"
    )

    test_X = test_y = None
    test_meta = None
    if not args.no_test_eval:
        print("Loading held-out test split for final evaluation only...")
        test_X, test_y, test_meta = load_test_data(
            args.test_csv, data.feature_names, data.classes
        )
        apply_scaler(test_X, data.scaler_mean, data.scaler_scale)
        print(f"Test rows: {len(test_y):,}")

    base_train_config = TrainConfig(
        rounds=args.rounds,
        local_epochs=args.local_epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        seed=args.seed,
        class_weight_mode=args.class_weight_mode,
        num_threads=args.num_threads,
    )
    selection_config = SelectionConfig(num_select=args.num_select)

    run_metadata = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scenario": args.scenario,
        "strategies": strategies,
        "partition_report": {
            "directory": str(partition_dir),
            "random_seed": report.get("random_seed"),
            "dirichlet_alpha": report.get("dirichlet_alpha"),
            "number_of_clients": report.get("number_of_clients"),
        },
        "context": context_meta,
        "train_config": base_train_config.__dict__,
        "selection_config": {
            "num_select": selection_config.num_select,
            "selection_file": (
                str(args.selection_file) if args.selection_file else None
            ),
            "selection_source": (
                "fixed_dashboard_selection"
                if selection_override is not None
                else "algorithmic_reselection_each_round"
            ),
            "weights": selection_config.weights,
            "eligibility": {
                "min_availability": selection_config.min_availability,
                "max_cpu_percent": selection_config.max_cpu_percent,
                "min_memory_available_mb": selection_config.min_memory_available_mb,
                "max_disk_percent": selection_config.max_disk_percent,
                "max_latency_ms": selection_config.max_latency_ms,
                "max_packet_loss_percent": selection_config.max_packet_loss_percent,
            },
        },
        "test_metadata": test_meta,
        "command_line": vars(args) | {
            "train_csv": str(args.train_csv),
            "test_csv": str(args.test_csv),
            "partitions_dir": str(args.partitions_dir),
            "output_dir": str(args.output_dir),
            "context_file": str(args.context_file) if args.context_file else None,
        },
    }
    (run_dir / "run_metadata.json").write_text(
        json.dumps(run_metadata, indent=4, default=json_default), encoding="utf-8"
    )

    summaries = []
    for strategy in strategies:
        print(f"\n{'=' * 60}\nExperiment: {args.scenario} / {strategy}\n{'=' * 60}")
        results = run_federated_experiment(
            data=data,
            contexts=fresh_contexts(base_contexts),
            strategy=strategy,
            selection_config=selection_config,
            train_config=base_train_config,
            select_fn=select_clients,
            scenario=args.scenario,
            test_X=test_X,
            test_y=test_y,
            selection_override=selection_override,
        )

        strategy_dir = run_dir / strategy
        strategy_dir.mkdir(parents=True, exist_ok=True)
        (strategy_dir / "results.json").write_text(
            json.dumps(results, indent=4, default=json_default), encoding="utf-8"
        )
        write_rounds_csv(results, strategy_dir / "rounds.csv")
        summaries.append(summary_row(results))

    (run_dir / "summary.json").write_text(
        json.dumps(summaries, indent=4, default=json_default), encoding="utf-8"
    )

    print(f"\n{'=' * 70}\nSUMMARY ({args.scenario})\n{'=' * 70}")
    header = (
        f"{'strategy':10} {'sel':>3} {'val_acc':>8} {'val_bf1':>8} "
        f"{'test_acc':>9} {'test_bf1':>9} {'comm_MB':>8} {'cpu_s':>8}"
    )
    print(header)
    for row in summaries:
        print(
            f"{row['strategy']:10} {row['num_select']:>3} "
            f"{(row['validation_accuracy'] or 0):>8.4f} "
            f"{(row['validation_macro_f1'] or 0):>8.4f} "
            f"{(row['test_accuracy'] or 0):>9.4f} "
            f"{(row['test_macro_f1'] or 0):>9.4f} "
            f"{row['communication_megabytes_total']:>8.2f} "
            f"{row['cpu_seconds_total']:>8.2f}"
        )

    print(f"\nTotal wall time: {time.perf_counter() - start:.1f}s")
    print(f"Results saved under {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
