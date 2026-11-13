"""Execute the existing client-selection algorithm and print JSON.

This CLI is the dashboard integration point.  It does not reimplement the
selection logic: it loads the real partition report and client context, calls
``greenfed_fl.selection.select_clients`` and prints the full explainable result.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from greenfed_fl.context import (
    generate_simulated_context,
    load_context_file,
)
from greenfed_fl.partitioning import load_partition_report
from greenfed_fl.paths import CONTEXT_DIR, PARTITIONS_DIR
from greenfed_fl.selection import (
    DEFAULT_WEIGHTS,
    SelectionConfig,
    select_clients,
)


def json_default(value):
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value)} is not JSON serializable")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default="iid", choices=["iid", "non_iid"])
    parser.add_argument(
        "--strategy",
        default="context",
        choices=["all", "random", "resource", "context"],
    )
    parser.add_argument("--num-select", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--round", type=int, default=0)
    parser.add_argument("--context-file", type=Path, default=None)
    parser.add_argument("--context-seed", type=int, default=42)
    parser.add_argument("--partitions-dir", type=Path, default=PARTITIONS_DIR)
    parser.add_argument("--min-availability", type=float, default=0.50)
    parser.add_argument("--max-cpu-percent", type=float, default=95.0)
    parser.add_argument("--min-memory-available-mb", type=float, default=128.0)
    parser.add_argument("--max-disk-percent", type=float, default=98.0)
    parser.add_argument("--max-latency-ms", type=float, default=1000.0)
    parser.add_argument("--max-packet-loss-percent", type=float, default=50.0)
    parser.add_argument(
        "--weights",
        default=None,
        help="JSON object overriding context-aware category weights",
    )
    parser.add_argument(
        "--weights-file",
        type=Path,
        default=None,
        help="Path to a JSON file overriding context-aware category weights",
    )
    args = parser.parse_args()

    partition_dir = args.partitions_dir / args.scenario
    report = load_partition_report(partition_dir)

    context_file = args.context_file
    if context_file is None:
        candidate = CONTEXT_DIR / f"{args.scenario}_context_seed{args.context_seed}.json"
        if candidate.is_file():
            context_file = candidate

    if context_file is not None:
        clients, context_meta = load_context_file(context_file)
        context_source = str(context_file)
    else:
        clients, context_meta = generate_simulated_context(
            report, seed=args.context_seed, jitter=False
        )
        context_source = "generated_in_memory"

    weights = dict(DEFAULT_WEIGHTS)
    if args.weights and args.weights_file:
        raise ValueError("Use either --weights or --weights-file, not both")
    weights_source = args.weights
    if args.weights_file is not None:
        weights_source = args.weights_file.read_text(encoding="utf-8")
    if weights_source:
        override = json.loads(weights_source)
        unknown = set(override) - set(weights)
        if unknown:
            raise ValueError(f"Unknown weights: {sorted(unknown)}")
        weights.update({name: float(value) for name, value in override.items()})

    config = SelectionConfig(
        num_select=args.num_select,
        min_availability=args.min_availability,
        max_cpu_percent=args.max_cpu_percent,
        min_memory_available_mb=args.min_memory_available_mb,
        max_disk_percent=args.max_disk_percent,
        max_latency_ms=args.max_latency_ms,
        max_packet_loss_percent=args.max_packet_loss_percent,
        weights=weights,
    )

    result = select_clients(
        clients,
        strategy=args.strategy,
        config=config,
        seed=args.seed,
        round_number=args.round,
    )
    payload = result.to_dict()

    context_by_id = {client.client_id: client for client in clients}
    for client_id, score in payload["clients"].items():
        context = context_by_id[client_id]
        score["context"] = context.to_dict()
        score["selected"] = client_id in payload["selected"]

    payload["rejected"] = [
        {
            "client_id": client_id,
            "reason": score["decision_reason"],
            "eligibility_reasons": score["eligibility_reasons"],
        }
        for client_id, score in payload["clients"].items()
        if client_id not in payload["selected"]
    ]
    payload["metadata"] = {
        "scenario": args.scenario,
        "seed": args.seed,
        "round": args.round,
        "context_source": context_source,
        "context": context_meta,
        "partition_report": {
            "random_seed": report.get("random_seed"),
            "dirichlet_alpha": report.get("dirichlet_alpha"),
            "number_of_clients": report.get("number_of_clients"),
            "all_records_assigned_once": report.get("all_records_assigned_once"),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "execution": "live_python_selection",
        "provenance_note": (
            "Resource and network context values are simulated for logical "
            "clients on shared hardware. Local sample counts and class coverage "
            "are derived from the saved partition report."
        ),
    }

    json.dump(payload, sys.stdout, indent=2, default=json_default)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # keep stdout machine-readable
        print(f"selection failed: {exc}", file=sys.stderr)
        sys.exit(1)
