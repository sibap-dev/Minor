# Limitations and Future Work

This document lists the constraints that affect interpretation and the work that would most improve the project. It is intentionally specific; vague caveats are not useful.

## 1. Measurement limitations

### 1.1 No energy or carbon measurement

There is no power meter, smart plug, or on-device power telemetry. The project reports CPU seconds and communication megabytes as proxies. It cannot state joules, watt-hours, or CO2e, and it cannot claim the system is "green" or more sustainable than centralized training.

**Future work:** measure per-device power during local training and communication, include network and server overhead, and apply a regional carbon-intensity profile. Report incremental energy above idle.

### 1.2 Shared host

All simulated clients run on one machine. CPU time and wall time are host-process measurements, not independent device measurements. Thread contention, caching, and scheduling affect the numbers, especially with `num_threads=4`.

**Future work:** deploy clients on separate physical devices or isolated containers with CPU quotas, and repeat the experiment to estimate host effects.

### 1.3 Communication is model-state only

The reported communication is `state_bytes * 2 * selected_clients * rounds`. It excludes protocol overhead, retries, serialization framing, telemetry, and any dataset transfer. It assumes full-state exchange with no compression.

**Future work:** measure actual bytes on the wire, add compression/quantization/sparsification baselines, and include straggler and retry behavior.

### 1.4 CPU scope is narrow

CPU seconds cover local training only. They exclude data loading, evaluation, selection scoring, server aggregation, and telemetry. These are small here but not zero.

**Future work:** instrument the full round, including data loading and aggregation, and report energy per round.

## 2. Experimental limitations

### 2.1 Short training budget

Two rounds and one local epoch are enough for comparison but not for convergence. Accuracy around 0.75 and macro-F1 around 0.39–0.48 reflect a short budget. Rankings may change with more rounds.

**Future work:** run 10–50 rounds, plot learning curves, and test whether context-aware selection catches up or falls further behind.

### 2.2 Three seeds and one partition seed

Standard deviations are descriptive, not confidence intervals. Non-IID random has a large accuracy standard deviation (0.0256), so small mean differences are not reliable. Only one partition seed (42) is used, so partition-level variance is unknown.

**Future work:** use at least five training seeds and three to five partition seeds; report confidence intervals and paired tests.

### 2.3 Simulated context

Resource and network values are generated profiles, not measurements from independent devices. Selection decisions are therefore tests of the policy logic against plausible context, not tests of a real deployment.

**Future work:** feed measured agent telemetry into the selector, including missing and stale values, and evaluate under real network variability.

### 2.4 Fixed, untuned weights

Context weights (0.30 resource, 0.20 network, 0.25 data, 0.15 fairness, 0.10 cost) were fixed before the full runs. No sensitivity analysis or weight search was performed. The negative result may partly reflect these weights.

**Future work:** grid or Bayesian sensitivity analysis over weights, and a learned or adaptive policy. Report the search protocol and keep the test set out of tuning.

### 2.5 Small client count

Five clients with `k=3` is coarse. Every decision selects 60% of the population, and the non-IID partition still gives each client 32–34 classes. Results may not transfer to dozens or hundreds of clients or to pathological one-class-per-client skew.

**Future work:** scale to 20–100 clients, include client drop-out and stragglers, and test more severe Dirichlet alpha values.

### 2.6 Model and task scope

The model is a small MLP on 39 pre-extracted flow features. It is not a packet-level detector, and it does not model temporal drift. The centralized Random Forest baseline has higher macro-F1 (0.5711 vs 0.4772 for two-round IID FedAvg), but the comparison is not controlled: different model, optimizer, and budget.

**Future work:** compare against a matched centralized MLP with the same budget, add temporal splits, and test sequence models if raw flow sequences are available.

### 2.7 Class imbalance

Rare classes have very few examples (for example, UPLOADING_ATTACK has 33 training rows and 6 test rows). Macro-F1 is noisy and the model performs poorly on these classes. Balanced class weighting is implemented but was not used in the recorded full runs.

**Future work:** run balanced-loss and resampling ablations, report per-class precision/recall, and avoid over-interpreting differences on classes with single-digit test support.

## 3. System limitations

### 3.1 Experiment management is not implemented

There are no endpoints to create, start, stop, or monitor experiments. The dashboard reads static aggregates and live telemetry; it does not control training.

**Future work:** add experiment CRUD, a job runner, status transitions, and read APIs for experiment telemetry. Keep training artifacts immutable and auditable.

### 3.2 Two backends

The Spring service is the primary dashboard backend; the Express service is the legacy ingest path used by the agent for disk and network data. They share a database and have overlapping `/api/clients` routes with different response shapes.

**Future work:** consolidate into one backend, or clearly separate ingest and presentation services with a single schema owner. Add contract tests.

### 3.3 Simulator duplicate registration

Restarting a simulator can register a new client instead of reusing an existing one. There is no idempotent registration key.

**Future work:** add a stable simulator identifier and upsert semantics, or a registration endpoint that returns existing credentials safely.

### 3.4 Missing error mapping

`ClientNotFoundException` is not mapped to 404, so `GET /api/clients/{id}` returns 500 for a missing client. Validation errors are not uniform across services.

**Future work:** add a `@RestControllerAdvice` with consistent error codes and problem details.

### 3.5 Security and privacy

- Dashboard endpoints are unauthenticated.
- Bearer tokens are long-lived and returned once; there is no rotation or recovery.
- CORS is open on the Express service.
- No TLS, rate limiting, secure aggregation, differential privacy, or poisoning defense.
- A malicious client can report false context or a corrupted update.

**Future work:** add authentication and authorization, token rotation, restrictive CORS, TLS, rate limits, update validation, and a threat model. Any privacy claim requires secure aggregation or differential privacy with a stated budget.

### 3.6 Frontend

The dashboard is a single large bundle with no code splitting, no component tests, and no browser end-to-end tests. It handles backend unavailability by showing empty/offline states, but this is manually verified only.

**Future work:** split routes, add component and smoke tests, and add accessibility checks.

### 3.7 Database and tests

Spring tests require a real PostgreSQL instance and the `DB_PASSWORD` environment variable. They are not hermetic and will fail without a database. There are no Express tests and no migration upgrade tests.

**Future work:** use Testcontainers or an isolated test schema, add ingest tests, and test Flyway upgrades from prior versions.

## 4. Literature and documentation limitations

- The literature review is focused, not systematic. Claims are limited to abstracts and publisher summaries.
- No formal meta-analysis was performed; cross-paper numbers are not directly comparable.
- The review excludes non-English work and most pre-2017 FL literature.
- The dataset split's original generation code is unavailable, so the exact stratification procedure cannot be attested. Temporal ordering is not guaranteed.
- Byte-level checksums of the CSV files are not stored.

## 5. What would most improve the project

Ordered by impact on credibility:

1. **Energy measurement** on real devices, even a small pilot, so sustainability claims are grounded.
2. **More rounds and seeds**, with learning curves and confidence intervals, so ranking claims are stable.
3. **Tuned or sensitivity-tested selection weights**, so the negative result is not an artifact of one arbitrary configuration.
4. **Hermetic backend tests** and end-to-end agent-to-dashboard tests.
5. **A matched centralized baseline** with the same model and budget.
6. **Consolidated backend** to remove the dual-ingest ambiguity.

Until then, the honest conclusion is narrow: partial participation reduced communication by 40% and CPU by roughly 24–47% in this setup, and context-aware selection did not outperform simpler baselines on accuracy. Those are the claims the evidence supports.
