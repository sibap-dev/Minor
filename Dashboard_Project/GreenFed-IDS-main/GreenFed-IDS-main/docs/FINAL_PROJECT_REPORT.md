# Final Project Report

**Project:** GreenFed-IDS — context-aware federated intrusion detection for IoT with sustainability accounting

**Date:** 2026-11-12

**Status:** Reproducible research prototype; dashboard and backend integrated; experimental claims limited to the recorded protocol.

## 1. Executive summary

GreenFed-IDS implements a federated learning pipeline for 34-class IoT intrusion detection on a CICIoT2023-derived dataset, compares four client-selection strategies under IID and non-IID partitions, and reports communication and CPU cost alongside accuracy. It also provides a monitoring backend and dashboard for client telemetry, dataset composition, partitions, and experiment results.

The main empirical finding is deliberately modest. Selecting three of five clients reduced model communication by exactly 40% and host CPU time by roughly 24–47% relative to full participation. Under IID, partial participation cost little accuracy. Under non-IID data, it cost about 1.4–1.9 percentage points. **Context-aware selection did not consistently outperform random or resource-aware selection**, and the project does not claim that it does. No energy or carbon measurement was possible; CPU seconds and communication megabytes are reported as proxies.

## 2. Objectives and outcome

| Objective | Outcome |
|---|---|
| Preserve existing dataset split and partitions | Preserved; validated coverage and no test leakage |
| Implement federated learning | PyTorch FedAvg with sample-weighted aggregation |
| Compare selection strategies | Four strategies × two scenarios × three seeds |
| Report sustainability proxies | Communication and CPU accounting, no energy claim |
| Integrate backend and dashboard | Spring Boot APIs + React dashboard + static artifacts |
| Provide honest documentation | Audit, literature, gap, design, experiments, APIs, tests, limitations |
| Avoid fabricated results | All reported numbers trace to run artifacts |

## 3. What was built

### 3.1 Federated learning package

`federated/greenfed_fl/`:

- `data.py`: CSV loading, label encoding, client construction, validation split, scaling, optional class weights.
- `model.py`: MLP `39 -> 128 -> 64 -> 34` with ReLU; 15,586 parameters; 62,344-byte state.
- `fedavg.py`: local SGD/Adam training, sample-weighted state aggregation, evaluation, per-round logging, communication and CPU accounting.
- `partitioning.py`: class-proportional IID and class-wise Dirichlet partitioning; exact-coverage validation; report generation.
- `context.py`: typed client context, provenance, simulated profiles.
- `selection.py`: `all`, `random`, `resource`, `context` strategies with eligibility, normalization, scoring, ranking, explanations, and fairness counters.
- `metrics.py`: accuracy, balanced accuracy, macro-F1, weighted F1.

CLIs: `validate_partitions.py`, `generate_context.py`, `run_experiment.py`, `repartition.py`, `aggregate_results.py`.

### 3.2 Backend

`server/` (Spring Boot 4.1.1, Java 21, PostgreSQL, Flyway):

- Client registration with hashed bearer tokens.
- Heartbeat and CPU/memory telemetry.
- Dashboard aggregates: latest-per-client CPU, memory, disk, latency, packet loss.
- Dataset summary from a packaged report.
- Integration tests against real PostgreSQL.

`api/` (Express 5) remains the legacy ingest for full CPU/memory/disk/network payloads from the Node agent.

### 3.3 Dashboard

`client/greenfed-dashboard-download/` (React + Vite):

- Overview with live client aggregates and federated-evaluation summary.
- Dataset Management with class matrix heatmap, shares, and rare-class panel.
- Partition views for IID and non-IID.
- Experiments view with IID/Non-IID switch, strategy table, metric cards, downloads, and explicit protocol caveats.
- Static experiment and partition artifacts under `public/data/`.

Production build succeeds (669.27 kB JS, 193.64 kB gzip; chunk-size warning only).

### 3.4 Agent and simulator

`agent/` (Node.js + systeminformation) collects host CPU, memory, disk, and network and posts to the Express ingest at a configurable interval.

`simulator/` (Node.js) registers simulated clients and posts generated resource, disk, and network telemetry. It registers new clients on each start, so repeated runs create duplicate client records; this is documented as a limitation, not a hidden behavior.

## 4. Dataset

| Item | Value |
|---|---|
| Source | CICIoT2023-derived, 39 flow features + `Label` |
| Training rows | 1,170,022 |
| Test rows | 290,874 |
| Classes | 34 |
| Missing values | 0 |
| Test usage | Final evaluation only |

The training set is long-tailed: DDoS flood classes dominate, BENIGN is about 2.34%, and several web/recon classes are below 0.4%. Overall accuracy is therefore reported with macro-F1, and rare-class results are treated cautiously. The original split-generation code is unavailable, so the report does not claim a specific stratification procedure or temporal ordering.

## 5. Partitions

| Scenario | Method | Clients | Seed | Alpha | Records | Duplicates | Class-share std |
|---|---|---:|---:|---:|---:|---:|---:|
| IID | Class-proportional | 5 | 42 | — | 1,170,022 | 0 | 0.1613 pp |
| Non-IID | Class-wise Dirichlet | 5 | 42 | 0.5 | 1,170,022 | 0 | 21.2734 pp |

Both scenarios assign every training row exactly once and never use the test split. The non-IID partition is strongly skewed in rows and labels but still gives each client 32–34 classes.

## 6. Experiment protocol

| Item | Value |
|---|---|
| Model | MLP 39→128→64→34 |
| Optimizer | Adam, lr 0.001 |
| Batch size | 256 |
| Local epochs | 1 |
| Rounds | 2 |
| Aggregation | Sample-weighted FedAvg |
| Participants | 5 for `all`, 3 for partial strategies |
| Seeds | 42, 43, 44 |
| Class weighting | None |
| Test use | Final evaluation only |
| Context | Simulated, seed 42 |

The matrix is 2 scenarios × 4 strategies × 3 seeds = 24 strategy runs, grouped into six run directories.

## 7. Results

Mean and sample standard deviation across three seeds.

| Scenario | Strategy | Test accuracy | Test macro-F1 | Comm. MB | CPU s |
|---|---|---:|---:|---:|---:|
| IID | all | 0.7531 and 0.0014 | 0.4772 and 0.0034 | 1.189 | 37.04 |
| IID | random | 0.7536 and 0.0019 | 0.4738 and 0.0010 | 0.713 | 24.34 |
| IID | resource | 0.7558 and 0.0055 | 0.4824 and 0.0122 | 0.713 | 27.97 |
| IID | context | 0.7529 and 0.0005 | 0.4767 and 0.0037 | 0.713 | 28.08 |
| Non-IID | all | 0.7256 and 0.0031 | 0.4188 and 0.0034 | 1.189 | 47.50 |
| Non-IID | random | 0.7118 and 0.0256 | 0.4122 and 0.0066 | 0.713 | 28.23 |
| Non-IID | resource | 0.7072 and 0.0107 | 0.3889 and 0.0082 | 0.713 | 25.33 |
| Non-IID | context | 0.7069 and 0.0108 | 0.3899 and 0.0115 | 0.713 | 27.01 |

Efficiency relative to full participation:

| Scenario | Strategy | Delta accuracy | Comm. reduction | CPU reduction |
|---|---|---:|---:|---:|
| IID | random | +0.05 pp | 40.0% | 34.3% |
| IID | resource | +0.27 pp | 40.0% | 24.5% |
| IID | context | −0.02 pp | 40.0% | 24.2% |
| Non-IID | random | −1.37 pp | 40.0% | 40.6% |
| Non-IID | resource | −1.84 pp | 40.0% | 46.7% |
| Non-IID | context | −1.87 pp | 40.0% | 43.1% |

### 7.1 Key observations

1. **Non-IID degrades full participation** by 2.75 pp accuracy and 5.84 pp macro-F1 relative to IID.
2. **Partial participation is nearly free under IID** (within 0.27 pp) but costs 1.37–1.87 pp under non-IID.
3. **Context-aware selection did not win.** It was 0.07 pp below random on IID and 0.49 pp below random on non-IID. Differences are small relative to seed variance.
4. **Resource-aware selection had the best IID mean accuracy** but the highest variance and the worst non-IID macro-F1.
5. **Communication savings are structural**: 3/5 clients gives exactly 40%, independent of strategy.
6. **CPU savings vary** (24–47%) because local dataset sizes and scheduling differ.

### 7.2 Centralized reference

The preserved centralized Random Forest reports test accuracy 0.7605 and macro-F1 0.5711 on the same test split. Two-round IID FedAvg reaches similar accuracy (0.7531) but much lower macro-F1 (0.4772). This is not a controlled comparison: models, optimizers, and budgets differ. It is a sanity reference only.

## 8. Sustainability

| Quantity | Status |
|---|---|
| Communication | Computed exactly from state size and participants |
| CPU seconds | Measured for local training process |
| Training wall time | Measured per client |
| Energy (J, Wh) | **Not measured** |
| Carbon (CO2e) | **Not measured** |

No power meter or device-level telemetry exists. The dashboard labels these as proxies. The honest claim is conditional: partial participation reduces model transfer by 40% and host CPU by roughly a quarter to a half in this setup; whether that lowers energy or carbon depends on unmeasured factors.

## 9. Literature and gap

The review covers FL foundations, non-IID effects, client selection, FL-IDS, CICIoT2023, and sustainability. It identifies a gap: few studies jointly compare full, random, resource-aware, and multi-factor context-aware selection on the same multi-class IoT dataset under IID and non-IID partitions with repeated seeds and cost accounting.

GreenFed-IDS addresses that gap with a controlled comparison and reports a negative result for context-aware superiority. This is consistent with the literature's emphasis that selection gains are workload-dependent.

## 10. Testing

| Check | Result |
|---|---|
| Python tests | 37 passed |
| Spring integration tests | 3 passed (requires PostgreSQL and `DB_PASSWORD`) |
| Dashboard build | Success |
| Partition validation | Both scenarios exact cover, 0 duplicates |
| Aggregate regeneration | JSON/CSV/MD reproduced |

The Spring tests are not hermetic: without a database and password they fail at Flyway. This is documented as a reproducibility caveat. There are no Express tests, no React component tests, and no end-to-end agent-to-dashboard test.

## 11. Limitations

- Two rounds, one local epoch, three seeds; short-budget results, not convergence.
- One partition seed; partition-level variance not estimated.
- Simulated context on a shared host; not independent devices.
- Fixed, untuned selection weights; no sensitivity analysis.
- No energy/carbon measurement.
- MLP on pre-extracted features; not packet-level or temporal.
- Class imbalance; rare-class metrics are noisy.
- No experiment management API; dashboard reads static aggregates.
- Dual backend (Spring + Express) with overlapping client routes.
- No privacy, secure aggregation, or poisoning defense.
- Unauthenticated dashboard endpoints; open CORS on Express.

See `LIMITATIONS_AND_FUTURE_WORK.md` for the full list and prioritized next steps.

## 12. Conclusion

GreenFed-IDS delivers a reproducible federated IDS evaluation and an integrated monitoring dashboard. The evidence supports a narrow efficiency claim: partial participation cuts communication by 40% and CPU by roughly 24–47%, with a small IID accuracy cost and a larger non-IID cost. It does not support a claim that context-aware selection is more accurate or more sustainable than simpler baselines. Reporting that negative result, with the protocol and its limits, is part of the contribution.

The highest-value next steps are real energy measurement, more rounds and seeds, selection-weight sensitivity analysis, and hermetic end-to-end tests.

## 13. Artifact index

| Path | Contents |
|---|---|
| `federated/greenfed_fl/` | Reusable FL, partitioning, context, selection code |
| `federated/run_experiment.py` | Experiment CLI |
| `federated/results/aggregate_full.{json,csv,md}` | Aggregated results |
| `federated/results/<run_id>/` | Per-run metadata, summaries, rounds |
| `federated/results/partition_validation.json` | Partition validation |
| `output/splits/{train,test}.csv` | Preserved dataset split |
| `output/partitions/{iid,non_iid}/` | Preserved partitions and reports |
| `server/` | Spring Boot backend |
| `api/` | Express ingest backend |
| `agent/` | Node telemetry agent |
| `simulator/` | Node simulated clients |
| `client/greenfed-dashboard-download/` | React dashboard and static artifacts |
| `docs/` | Audit, literature, gap, design, experiments, sustainability, architecture, dataset, partitioning, API, testing, limitations, and this report |

## 14. Reproduction checklist

1. Confirm Python 3.13, PyTorch, PostgreSQL, Java 21, Node.js 22.
2. Set `DB_PASSWORD` for the backend; ensure `greenfed_monitor` exists.
3. Validate partitions: `python federated/validate_partitions.py --methods iid,non_iid`.
4. Generate context: `python federated/generate_context.py --scenario iid --seed 42`.
5. Run experiments for seeds 42–44 and both scenarios with `--tag full`.
6. Aggregate: `python federated/aggregate_results.py --tag full`.
7. Run Python tests: `cd federated; python -m pytest -q`.
8. Run Spring tests with `DB_PASSWORD` set: `.\mvnw.cmd test`.
9. Build dashboard: `npm run build` in `client/greenfed-dashboard-download`.
10. Start PostgreSQL, Spring server, and dashboard; verify `/api/dashboard/overview` and the Experiments view.

## 15. Documentation map

- `PROJECT_AUDIT.md`: initial repository audit.
- `IMPLEMENTATION_STATUS.md`: phase-by-phase status and evidence.
- `LITERATURE_REVIEW.md`: verified sources and synthesis.
- `RESEARCH_GAP.md`: gap statement and research questions.
- `SYSTEM_ARCHITECTURE.md`: components, data flow, ports, limits.
- `DATASET_METHODOLOGY.md`: dataset provenance, features, class distribution.
- `PARTITIONING_METHODOLOGY.md`: IID/Dirichlet algorithms and validation.
- `CONTEXT_AWARE_SELECTION_DESIGN.md`: eligibility, scoring, strategies, limitations.
- `FEDERATED_LEARNING_EXPERIMENTS.md`: protocol and full results.
- `SUSTAINABILITY_EVALUATION.md`: proxy definitions and honest scope.
- `API_DOCUMENTATION.md`: Spring and Express endpoints.
- `TESTING_REPORT.md`: commands, results, gaps.
- `LIMITATIONS_AND_FUTURE_WORK.md`: constraints and next steps.
