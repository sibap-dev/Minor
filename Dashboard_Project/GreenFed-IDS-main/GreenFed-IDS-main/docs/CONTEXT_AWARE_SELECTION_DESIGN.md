# Context-Aware Selection Design

This document specifies the client-selection policies used in the experiments. The design goal is explainability and controlled comparison, not a new optimization algorithm.

## 1. Inputs

Each logical client is represented by `ClientContext` (`federated/greenfed_fl/context.py`) with:

| Field | Range | Meaning |
|---|---|---|
| `cpu_percent` | 0–100 | Current CPU utilization |
| `memory_percent` | 0–100 | Memory utilization |
| `memory_available_mb` | ≥ 0 | Available memory |
| `disk_percent` | 0–100 | Disk utilization |
| `latency_ms` | ≥ 0 | Network latency |
| `packet_loss_percent` | 0–100 | Packet loss |
| `bandwidth_mbps` | ≥ 0 | Bandwidth |
| `jitter_ms` | ≥ 0 | Latency jitter |
| `availability` | 0–1 | Availability probability |
| `local_samples` | ≥ 0 | Training rows on the client |
| `class_coverage` | ≥ 0 | Number of distinct classes present |
| `total_classes` | ≥ 0 | Number of classes in the global label set |
| `rounds_since_selected` | ≥ 0 | Fairness counter |
| `enabled` | boolean | Administrative enable flag |

Every contextual field carries provenance: `measured`, `simulated`, `estimated`, or `unavailable`. In the current experiments, resource and network values are **simulated**; `local_samples` and `class_coverage` are derived from the real partition reports and marked `measured`. The context file metadata repeats this warning.

Five simulated profiles are used:

| Profile | CPU | Memory | Latency | Loss | Bandwidth | Availability |
|---|---:|---:|---:|---:|---:|---:|
| Edge gateway, strong | 25% | 42% | 22 ms | 0.4% | 90 Mbps | 0.98 |
| Sensor hub, moderate | 55% | 64% | 65 ms | 2.5% | 35 Mbps | 0.90 |
| Constrained camera | 86% | 81% | 145 ms | 7.5% | 12 Mbps | 0.70 |
| LAN node, low load | 30% | 48% | 38 ms | 1.0% | 70 Mbps | 0.95 |
| Remote node, weak network | 62% | 72% | 310 ms | 14.0% | 5 Mbps | 0.62 |

Small seeded jitter is applied during generation and values are clipped to valid ranges. Profiles are assigned to clients in partition-report order.

## 2. Eligibility

Before scoring, hard constraints are applied (`SelectionConfig` defaults):

| Constraint | Default |
|---|---:|
| Minimum availability | 0.50 |
| Maximum CPU | 95% |
| Minimum available memory | 128 MB |
| Maximum disk | 98% |
| Maximum latency | 1000 ms |
| Maximum packet loss | 50% |

A client is eligible only if it is enabled and satisfies every available constraint. Missing metrics do not automatically disqualify a client; they are recorded in `missing_metrics` and handled as neutral values during normalization.

If fewer than `k` clients are eligible, the ranking falls back to the highest-scoring ineligible clients until `k` are selected, and the result records `constraints_relaxed=true` with a note. This prevents a round from silently selecting fewer clients than requested, while making the relaxation visible.

## 3. Normalization

All criteria are min-max normalized across the current candidate set to `[0, 1]`:

- Higher-is-better: `(x - min) / (max - min)`.
- Lower-is-better: `1 - (x - min) / (max - min)`.
- Missing value: `0.5`.
- No spread (`max == min`): every candidate gets `0.5`.

Normalization is computed separately per round over the participating candidate pool. Scores are therefore relative within a round, not comparable across rounds. This is intentional: selection is a ranking problem, not an absolute utility measurement.

## 4. Category scores

### 4.1 Resource

```
cpu_headroom      = 100 - cpu_percent
memory_headroom   = 100 - memory_percent
memory_score      = mean(normalize(memory_headroom), normalize(memory_available_mb))
resource_score    = 0.5 * normalize(cpu_headroom) + 0.5 * memory_score
```

### 4.2 Network

```
network_score = 0.45 * normalize_inverse(latency_ms)
              + 0.30 * normalize_inverse(packet_loss_percent)
              + 0.15 * normalize(bandwidth_mbps)
              + 0.10 * normalize_inverse(jitter_ms)
```

### 4.3 Data

```
log_samples   = log1p(local_samples)
coverage      = class_coverage / total_classes
data_score    = 0.60 * normalize(log_samples) + 0.40 * normalize(coverage)
```

Using `log1p` reduces the dominance of row count among clients whose sizes differ by an order of magnitude.

### 4.4 Fairness

```
fairness_raw  = rounds_since_selected / max(rounds_since_selected)
fairness_score = normalize(fairness_raw)
```

A client that has not been selected for many rounds scores higher. Counters reset to zero when selected and increment otherwise.

### 4.5 Cost proxy

```
cost_proxy = log1p( (local_samples * (0.25 + cpu_percent / 100)) / max(bandwidth_mbps, 0.5) )
cost_score = normalize(cost_proxy)   # higher means more expensive
```

This is explicitly a **relative proxy**, not measured energy. It increases with local dataset size and CPU load and decreases with bandwidth. It is used for ranking only.

## 5. Strategies

### 5.1 `all` (full participation)

Selects every enabled client. This is conventional FedAvg and serves as the cost and accuracy reference.

### 5.2 `random`

Uniform random selection without replacement from enabled clients, using `numpy.random.default_rng(seed + round_number)`. It ignores resource state and data. It is the main simple baseline.

### 5.3 `resource`

```
score = 0.70 * resource_score + 0.30 * (1 - cost_score)
```

Resource-aware but network- and fairness-blind. It tests whether CPU/memory headroom plus cost avoidance is sufficient.

### 5.4 `context`

Default weights:

| Component | Weight |
|---|---:|
| Resource | 0.30 |
| Network | 0.20 |
| Data | 0.25 |
| Fairness | 0.15 |
| Cost | 0.10 |

```
score = 0.30 * resource_score
      + 0.20 * network_score
      + 0.25 * data_score
      + 0.15 * fairness_score
      - 0.10 * cost_score
```

The cost term is subtracted because `cost_score` is higher for more expensive clients. The default weights sum to 1.0. `SelectionConfig` validates non-negativity and that the cost weight is at most 1.0, but it does not enforce the sum, so changing weights also changes the score scale; this is a known design limitation.

## 6. Ranking and tie-breaking

Eligible clients are sorted by descending score, then by `client_id` ascending as a deterministic tie-break. The top `k` are selected (`k = 3`). Every client receives a `ClientScore` record with:

- eligibility and rejection reasons;
- missing metrics;
- numeric score;
- per-component contributions;
- cost proxy;
- selected flag, rank, and decision reason.

This makes a selection reproducible and inspectable rather than a black-box choice.

## 7. Complexity

For `n` candidates and fixed criteria, scoring is `O(n)` and sorting is `O(n log n)` per round. With five clients the overhead is negligible relative to local training. The design would need batching or approximate ranking at hundreds of clients.

## 8. Why these weights

The weights encode a deployment preference: resource headroom matters most, followed by data usefulness and network quality, with fairness as a smaller corrective term and cost as a penalty. They were fixed before the full experiments and were not tuned on the test set. No weight search was performed, so the results do not represent an optimized context policy.

This is important for interpretation. If context-aware selection underperforms, it may be because the weights are not optimal, because the simulated context does not match the training bottleneck, or because partial participation itself costs accuracy under non-IID data. The experiment cannot separate these causes.

## 9. Observed behavior

Across the full runs (three seeds), context-aware selection:

- reduced communication by 40% and CPU by about 24% (IID) and 43% (non-IID) relative to full participation;
- was within 0.02 percentage points of full participation on IID accuracy;
- was 1.87 percentage points below full participation on non-IID accuracy;
- did not consistently beat random or resource-aware selection.

These are descriptive results from the recorded runs, not a claim that context-aware selection is superior. See `FEDERATED_LEARNING_EXPERIMENTS.md` and `SUSTAINABILITY_EVALUATION.md`.

## 10. Limitations and failure modes

- Simulated context: profiles are logical, not measured from independent devices.
- Relative normalization: scores depend on the candidate pool and cannot be compared across rounds.
- Fixed weights: no tuning, no sensitivity analysis, no learned policy.
- Cost proxy: not energy; ignores memory and disk cost, network transfer time, and straggler effects.
- Fairness is a counter, not a formal fairness guarantee; it can conflict with data or resource scores.
- Constraint relaxation can select an ineligible client; the flag is recorded but downstream training does not adapt.
- Small client count: five candidates and `k=3` means each decision is coarse.
- No poisoning or adversarial context: a client could misreport its state.
- Independence assumption: criteria are combined linearly, ignoring interactions (for example, low bandwidth may matter more when local data is large).

## 11. Reproduction

```powershell
python federated/generate_context.py --scenario iid --seed 42
python federated/run_experiment.py --scenario iid --strategy context --seed 42 --rounds 2 --tag demo
```

Per-client score records are written in each run's `results.json` under the selection details, so a selection can be audited round by round.
