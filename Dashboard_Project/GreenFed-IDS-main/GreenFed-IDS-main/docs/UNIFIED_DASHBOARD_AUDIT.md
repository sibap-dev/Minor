# Unified Dashboard Audit and Implementation Plan

This audit reflects the repository state before the unified-dashboard change. The
dashboard is the single interface to be extended; no second frontend is created.

## 1. Component-to-feature mapping

| Component | Implemented behaviour | Current dashboard exposure | Main gap |
|---|---|---|---|
| `client/greenfed-dashboard-download/` React + Vite | Overview telemetry, dataset reports, partition reports, static experiment aggregates | Yes | Demo fallback data; no selection/training/simulation controls; navigation does not match research workflow |
| `server/` Spring Boot :4000 | Client registration, token auth, resource telemetry, heartbeat, dashboard aggregates, dataset summary | Yes (Vite proxy) | No disk/network ingest in Spring, no selection/training orchestration, no experiment history API, no simulator control |
| `api/` Express :5000 | Full telemetry ingest (resource/disk/network), client registration, heartbeat | Indirectly through DB | Second ingest path; simulator/agent depend on it; no frontend proxy |
| `simulator/` Node | Registers 5 clients on every start, posts generated resource/disk/network telemetry | No | Duplicate client registrations; no dashboard start/stop; no latency/loss/availability profiles; points at Express |
| `agent/` Node | Host CPU/memory/disk/network collection | No direct control | Posts to Express, not Spring; not represented as a workflow stage |
| `federated/` Python + PyTorch | Partitioning, context generation, explainable selection, FedAvg, evaluation, aggregation | Static results only | No HTTP/CLI bridge for dashboard selection; no way to force training to use a dashboard selection |
| PostgreSQL | Clients, credentials, experiments, telemetry, disk/network samples | Through Spring aggregates | `experiments` tables exist but no UI/API lifecycle |
| `federated/results/` | 7 run directories, 24 strategy runs, verified aggregates | Static `public/data/experiments` | No live run history API; no new executions from dashboard |
| `docs/` | Architecture, methodology, experiments, testing, limitations | No | Must be updated after implementation |

## 2. Existing functional features

- Live overview metrics and client rows from Spring/PostgreSQL.
- Dataset summary and saved IID/non-IID partition reports.
- Static experiment comparison with IID/non-IID switch and downloads.
- Explainable selection implementation (`all`, `random`, `resource`, `context`) with
  hard eligibility, relaxed-fallback notes, scores, contributions, rejection reasons.
- Reproducible FedAvg runs with per-round validation, final test evaluation,
  communication volume, CPU seconds, and run metadata.
- Client registration and bearer-token telemetry authentication.
- Node simulator and agent telemetry collection.
- Historical run directories are immutable and already archived.

## 3. Incomplete, duplicate, or misleading features

1. **Demo fallback data is presented as live UI data.** `data.js` supplies fake
   clients, timeseries, and activity items. The dashboard must show
   `UNAVAILABLE` instead of invented values.
2. **No end-to-end workflow.** Selection and training exist only as Python CLIs;
   the dashboard only reads saved aggregate JSON.
3. **Selected clients are not passed to training.** `run_experiment.py` always
   reselects inside `fedavg.run_federated_experiment`.
4. **Simulator creates duplicate clients on restart.** It registers five new DB
   rows every launch and keeps tokens only in memory.
5. **Simulator does not exercise the five configured context profiles.** Values
   are independent random ranges, not the edge-gateway/sensor/camera/lan/remote
   profiles used by context generation.
6. **Latency, packet loss, bandwidth, and availability are not visible in the
   clients table.** Network data exists in the DB but the query/UI omits it.
7. **Spring and Express have overlapping telemetry responsibilities.** Spring
   accepts resource-only telemetry; Express accepts resource/disk/network.
   Simulator/agent target Express while the dashboard targets Spring.
8. **Experiment tables are unused.** `experiments`, `experiment_clients`, and
   `experiment_events` have no lifecycle API or UI.
9. **Navigation mixes monitoring and research concepts** (`Resource metrics`,
   `Network`, `Dataset Management`) and omits selection, training, and advanced
   configuration.
10. **Dataset page is dense.** Class tables dominate the normal view; partition
    comparison is not summarised side by side.
11. **No provenance vocabulary in the UI.** "Measured"/"Simulated" is a single
    string; availability and derived values are not labelled.
12. **No live timeseries API.** The overview chart uses fabricated `data.js`
    series rather than DB samples.

## 4. Preserved behaviour and artifacts

- `federated/greenfed_fl/*` algorithms and defaults are preserved.
- All existing `federated/results/*` directories remain untouched.
- Existing partition artifacts in `output/partitions/` remain untouched.
- Existing train/test split and dataset report remain untouched.
- Existing Spring client/telemetry/dataset/dashboard APIs remain available.
- Existing Python and Spring tests remain part of acceptance.
- Express API is not deleted; it remains a legacy/alternate ingest path.
- No fabricated metrics or training progress will be introduced.

## 5. Proposed unified workflow

```text
Dataset -> Client Simulation -> Client Context -> Client Selection
        -> Local Training -> Global Aggregation -> Evaluation
        -> Experiment Comparison
```

### Backend integration

1. Add `federated/select_clients.py` as a JSON CLI over the existing
   `select_clients` implementation.
2. Add `--selection-file` and `--run-id` options to `run_experiment.py`.
   The selection file fixes the exact dashboard-selected clients for every round.
3. Spring `WorkflowService` invokes the Python CLIs (no algorithm reimplementation),
   stores selection JSON under `federated/results/selections/`, starts training as
   an asynchronous child process, tracks logs/status, and never overwrites a run.
4. Spring `ExperimentHistoryService` scans `federated/results/*` to serve historical
   runs and new dashboard executions separately.
5. Spring `SimulationService` starts/stops the existing Node simulator with a
   fixed command and environment. The simulator writes a credential cache and
   reuses registrations on restart.
6. Extend Spring telemetry to persist disk/network fields and availability so the
   simulator can post to the primary Spring ingest.
7. Add dashboard timeseries and richer client fields (latency, bandwidth, packet
   loss, availability, provenance).

### Frontend organisation

Use the existing React application and visual language, reorganised into:

1. **Overview** - live counts, dataset facts, current job, current selection,
   latest verified model result, workflow diagram.
2. **Dataset** - CICIoT2023 facts, split, class distribution, IID/non-IID
   comparison, client allocation, validation.
3. **IoT Clients** - start/stop simulation, five profiles, resource/network
   metrics, availability, REAL/SIMULATED/DERIVED/UNAVAILABLE labels.
4. **Client Selection** - strategy, participant count, thresholds/weights,
   execute, selected/rejected explanations, scores and contributions.
5. **Federated Learning** - configuration, exact selected-client handoff, job
   progress, client/aggregation status, round metrics from real results.
6. **Experiments & Results** - new runs, history, rerun, comparison, IID/non-IID,
   downloads, historical vs newly executed labels.
7. **Advanced Configuration** - defaults, thresholds, logs, API diagnostics,
   raw metadata, debugging details.

### Acceptance tests

- Existing Python tests and Spring tests continue to pass.
- Selection API output matches `select_clients` exactly and includes rejection
  reasons and relaxed-fallback notes.
- Training receives and logs the selection ID and selected client IDs; results
  record `fixed_dashboard_selection`.
- Simulator restart reuses cached credentials and does not add duplicate rows.
- New experiment directories never overwrite existing results.
- Frontend production build succeeds.
- No fabricated live values remain in the normal UI.
