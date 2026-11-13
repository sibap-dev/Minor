# Sustainability Evaluation

This document explains what the project measures, how the proxies are computed, what the results show, and what cannot be concluded. The short version: communication volume and CPU time are reported; energy and carbon are **not** measured.

## 1. Why proxies are necessary

FL carbon studies show that communication can be a large or dominant share of emissions and that FL is not automatically greener than centralized training [1]. Energy/carbon analyses show that learner-population selection can reduce energy, but the result depends on the model and infrastructure [2]. A defensible sustainability claim requires either a power meter or a documented model of energy use.

This project has no power meter, no smart plug, and no per-device hardware telemetry at the socket level. All simulated clients run on one host. Therefore the project reports two measured/computed quantities:

1. **Communication volume**, computed exactly from model state size and participant count.
2. **CPU seconds**, measured for the Python training process with `time.process_time()` around local training.

It also reports training wall time per round. It does **not** report joules, watt-hours, or CO2e.

## 2. Measurement definitions

### 2.1 Communication

The model state is serialized size:

```
state_bytes = sum(tensor.numel() * tensor.element_size())
```

For the MLP `39 -> 128 -> 64 -> 34`:

| Component | Calculation | Bytes |
|---|---|---:|
| Layer 1 weights | 39 × 128 × 4 | 19,968 |
| Layer 1 bias | 128 × 4 | 512 |
| Layer 2 weights | 128 × 64 × 4 | 32,768 |
| Layer 2 bias | 64 × 4 | 256 |
| Layer 3 weights | 64 × 34 × 4 | 8,704 |
| Layer 3 bias | 34 × 4 | 136 |
| **Total** | | **62,344** |

Per round, the server sends the global state to each selected client and receives an updated state:

```
round_bytes = state_bytes × 2 × selected_clients
```

Total:

```
communication_bytes_total = sum over rounds of round_bytes
```

This counts model-state transfer only. It excludes protocol overhead, retries, serialization framing, telemetry, and dataset transfer (none occurs). It also assumes every client sends and receives the full state; there is no compression, sparsification, or quantization.

For the recorded runs:

| Strategy | Clients/round | Rounds | Bytes | MB |
|---|---:|---:|---:|---:|
| `all` | 5 | 2 | 1,246,880 | 1.189 |
| `random` | 3 | 2 | 748,128 | 0.713 |
| `resource` | 3 | 2 | 748,128 | 0.713 |
| `context` | 3 | 2 | 748,128 | 0.713 |

The 40% reduction is structural:

```
1 - (3 / 5) = 0.40
```

It is not an empirical optimization. Any strategy that selects three of five clients achieves the same communication reduction for a fixed state size.

### 2.2 CPU time

Each local training call records:

```
cpu_seconds = process_time_after - process_time_before
```

`process_time` measures CPU time consumed by the process, not wall-clock time and not energy. Summing over selected clients and rounds gives `cpu_seconds_total`.

Scope: the Python training process on the host. It includes local forward/backward passes and optimizer steps for the selected clients. It excludes data loading, evaluation, selection scoring, and server aggregation (these are small in this setup but not zero). Because all clients share the host, CPU time is not partitioned by physical device.

### 2.3 Training wall time

`training_seconds_total` sums per-client training durations measured with `time.perf_counter()`. On a shared host this is affected by thread scheduling and contention, especially with `num_threads=4` and multiple clients trained sequentially.

## 3. Results

From `aggregate_full.md`, three seeds per cell:

| Scenario | Strategy | Comm. MB | CPU s | Comm. reduction | CPU reduction |
|---|---|---:|---:|---:|---:|
| IID | all | 1.189 | 37.04 | 0.0% | 0.0% |
| IID | random | 0.713 | 24.34 | 40.0% | 34.3% |
| IID | resource | 0.713 | 27.97 | 40.0% | 24.5% |
| IID | context | 0.713 | 28.08 | 40.0% | 24.2% |
| Non-IID | all | 1.189 | 47.50 | 0.0% | 0.0% |
| Non-IID | random | 0.713 | 28.23 | 40.0% | 40.6% |
| Non-IID | resource | 0.713 | 25.33 | 40.0% | 46.7% |
| Non-IID | context | 0.713 | 27.01 | 40.0% | 43.1% |

Observations:

- Communication savings are exactly 40% for all partial strategies, as expected.
- CPU savings range from about 24% to 47%. They are not proportional to communication savings because client data sizes differ and CPU time scales with local rows and local epochs.
- Non-IID CPU totals are higher than IID for full participation (47.50 s vs 37.04 s). The non-IID partition has clients with larger local datasets (up to 325,213 rows vs about 234,000 in IID), and all clients participate in the `all` strategy.
- Partial strategies reduce CPU under both scenarios, but the ranking among them is not stable across scenarios (random best on IID, resource best on non-IID).

## 4. What this supports

Supported:

- Selecting three of five clients reduces model-transfer volume by 40% for this model and round count.
- Partial participation reduces host CPU time by roughly a quarter to a half in these runs.
- The communication saving can be computed exactly and audited from the recorded state size and participant counts.
- Full participation costs more communication and CPU than partial participation in this setup.

Not supported:

- A claim that the system is "green", "carbon-neutral", or more sustainable than centralized training.
- A claim about joules, watt-hours, or CO2e.
- A claim that context-aware selection is the most energy-efficient policy. It was not; resource-aware and random had lower CPU means in one or both scenarios.
- A claim that client devices save energy. No device-level power was measured.
- A claim that communication dominates total energy. The project did not measure energy shares.

## 5. Interpretation

The honest conclusion is conditional:

> At three of five clients over two rounds, model communication fell by 40% and host CPU time fell by roughly 24–47% relative to full participation. Context-aware selection did not produce the largest CPU or accuracy benefit. Whether these reductions translate into lower energy or carbon depends on device power, network energy intensity, and data-center overhead, none of which were measured.

This is consistent with the literature's warning that FL sustainability is configuration-dependent and must be measured rather than assumed [1], [2].

## 6. If a real energy study were added

A credible follow-up would need:

1. Per-device power measurement (external meter or on-device rail) during local training and communication.
2. Network energy intensity for the actual link, including switches and gateways.
3. Server-side energy for aggregation, or a stated allocation method.
4. Idle and baseline power so incremental energy can be separated.
5. A carbon-intensity profile for the time and region of execution.
6. Repeated runs to estimate variance.

Without these, CPU seconds and communication megabytes should be labelled as proxies, which is what the dashboard and this document do.

## 7. Reproducibility

Per-run resource values are in each run's `results.json` under `resource_summary`:

```json
{
  "communication_bytes_total": 1246880.0,
  "communication_megabytes_total": 1.189117431640625,
  "cpu_seconds_total": 38.234375,
  "training_seconds_total": 12.82561210001586,
  "resource_scope": "host_training_process",
  "energy_measured": false
}
```

The aggregate tables are regenerated with:

```powershell
python federated/aggregate_results.py --tag full
```

## References

[1] X. Qiu, T. Parcollet, J. Fernandez-Marques, et al., "A first look into the carbon footprint of federated learning," *Journal of Machine Learning Research*, 24(129):5899–5921, 2023. arXiv:2102.07627

[2] S. Savazzi, V. Rampa, S. Kianoush, and M. Bennis, "An Energy and Carbon Footprint Analysis of Distributed and Federated Learning," *IEEE Transactions on Green Communications and Networking*, 7(1):248–264, 2023. https://doi.org/10.1109/TGCN.2022.3186439
