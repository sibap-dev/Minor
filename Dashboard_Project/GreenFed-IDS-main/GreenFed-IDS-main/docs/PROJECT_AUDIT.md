# GreenFed-IDS — Project Audit

Date: 2026-11-12
Auditor: repository inspection performed directly on the local workspace; no claims below are based on unverified assumptions.

## 1. Workspace layout (important)

The git repository root is `D:\vs code\Minor_Project`. The GreenFed-IDS application lives in the nested folder:

```
D:\vs code\Minor_Project\GreenFed-IDS-main\GreenFed-IDS-main
```

The nested folder is currently **untracked** by git (`git status` reports `?? GreenFed-IDS-main/`). Dataset artifacts, the centralized Random Forest baseline and the `federated/` task folder live at the repository root, not inside the nested app folder:

| Location | Contents | Git status |
|---|---|---|
| `Minor_Project/output/splits/train.csv`, `test.csv` | Prepared CICIoT2023 split | Tracked via `.gitignore` rules? present locally |
| `Minor_Project/models/greenfed_random_forest.joblib` | Centralized RF model | Present locally |
| `Minor_Project/reports/*.csv` | RF evaluation and dataset audit reports | Tracked |
| `Minor_Project/federated/` | **Only `README.md`** | Tracked |
| `Minor_Project/GreenFed-IDS-main/GreenFed-IDS-main/` | Monitoring platform + partitioning + dashboard + Spring Boot | **Untracked** |

A safe branch `greenfed-implementation` was created in the parent repository. No files were deleted or rewritten during the audit.

## 2. Existing architecture

There are **two backend implementations**, which is a major integration issue:

1. **Node.js/Express API** — `api/` — port `5000` (default in `api/src/server.js`).
   - `GET /api/health`, `GET /api/db-health`
   - `POST /api/clients` (registration + token)
   - `POST /api/heartbeat`
   - `POST /api/telemetry`
   - No dashboard read endpoints, no experiment endpoints, no exports.
2. **Spring Boot API** — `server/` — port `4000` (`application.properties`).
   - `GET /api/datasets/summary` (reads classpath `dataset/dataset_report.json`)
   - `GET /api/clients`, `GET /api/clients/{id}`, `POST /api/clients`
   - `POST /api/agent/heartbeat`, `POST /api/agent/telemetry`
   - Actuator health/info
   - Flyway migrations V1–V4

The React dashboard (`client/greenfed-dashboard-download`) proxies `/api` to `http://127.0.0.1:4000` (Spring Boot), but:
- It calls `GET /api/dashboard/overview` and `GET /api/clients`. The former is **not implemented in either backend**.
- Live monitoring data is ingested through the Express API on port 5000, which the dashboard proxy does not reach.
- The Dataset Management page does work against Spring Boot `GET /api/datasets/summary` **when Spring Boot is running**.
- Partition reports are loaded as static files from `client/.../public/data/partitions/{iid,non_iid}/partition_report.json`; these are byte-identical copies of `output/partitions/*/partition_report.json` (verified by SHA-256).

### Data flow as built

```
Real agent (agent/) ─┐
Simulator (simulator/) ─┼─► Express API :5000 ─► PostgreSQL greenfed_monitor
                        │
Spring Boot :4000 ─► reads dataset_report.json for /api/datasets/summary
                    └► clients + resource_samples (JPA)

React dashboard ─► Vite proxy :4000 ─► /api/datasets/summary, /api/clients
                └► static /data/partitions/*/partition_report.json
```

### Federated learning

`federated/` contains **only a README with requirements**. No Python source exists in the repository for the MLP, Flower clients, FedAvg aggregation, partitioning loader, or experiment runner. The historical FedAvg numbers quoted in the project brief (IID round 1 accuracy 0.7449, etc.) therefore **cannot be reproduced or verified from the current repository**. They are treated as unverified historical records and must not be presented as verified results.

The partitioning implementation exists and is real:
- `scripts/partitioning/partition_dataset.py` (IID + Dirichlet non-IID, 5 clients, seed 42, alpha 0.5)
- `inspect_partitions.py`, `compare_class_distributions.py`, `create_comparison_report.py`
- `output/partitions/{iid,non_iid}/client_{1..5}_indices.npy` + `partition_report.json`
- `output/partitions/comparison_report.json`

## 3. Verified completed components

| Component | Evidence |
|---|---|
| CICIoT2023 split preserved | `output/splits/train.csv` = 1,170,022 rows; `test.csv` = 290,874 rows; 40 columns incl. `Label`; 39 numeric features |
| Train label set | 34 classes confirmed from actual `train.csv` |
| Partition validation | Both reports have `all_records_assigned_once: true`; IID counts 234,019 / 234,012 / 234,003 / 233,997 / 233,991; Non-IID 220,029 / 232,318 / 271,630 / 325,213 / 120,832 |
| Dashboard partition copies | SHA-256 identical to the source reports |
| Centralized RF artifacts | `models/greenfed_random_forest.joblib`, `reports/random_forest_classification_report.csv`, `reports/random_forest_confusion_matrix.csv` |
| Dataset summary API | `DatasetController` + `DatasetService` + `dataset_report.json` |
| Client registration and hashed token storage (Spring + Express) | source inspection |
| Resource telemetry (CPU/memory) in Spring; CPU/memory/disk/network in Express | source inspection |
| Real agent + simulator | source inspection |
| Flyway schema V1–V4 | source inspection |
| React/Vite dashboard builds (node_modules present) | to be re-verified during this work |

The historical RF results (accuracy 0.7605, balanced accuracy 0.5938, macro-F1 0.5711, weighted-F1 0.7537) are consistent with the saved per-class report but were not re-trained during this audit (training cost). They remain historical artifacts.

## 4. Incomplete or missing components

1. **Federated learning implementation is entirely missing** (highest research priority).
2. **Context-aware client selection** is not designed or implemented.
3. **No federated experiments / results** exist in the repository.
4. **Dashboard overview endpoint** `/api/dashboard/overview` missing.
5. **Dashboard live monitoring is disconnected** (Express ingest on 5000 vs Spring proxy on 4000; no telemetry read API).
6. **Experiment management** has schema tables (`experiments`, `experiment_clients`, `experiment_events`) but no APIs.
7. **No automated tests** beyond `ServerApplicationTests.contextLoads` (which requires a live PostgreSQL).
8. **No Python tests** for partitioning, data loading, selection, FedAvg, metrics.
9. **No literature review or research gap document.**
10. **No final documentation set.**

## 5. Bugs and technical debt

| ID | Issue | Impact |
|---|---|---|
| B1 | No FedAvg code despite README/results | Research contribution cannot be evaluated |
| B2 | Dashboard calls unimplemented `/api/dashboard/overview` | Sidebar shows "not connected" permanently |
| B3 | Two backends on different ports | Live telemetry never reaches dashboard proxy |
| B4 | `scripts/partition_dataset.py` hardcodes client count, alpha, seed | No experiment matrix |
| B5 | Partition script only loads `Label`; no reusable client data loader | Federated training needs features per client |
| B6 | `DatasetService` serves only a static classpath JSON | No partition/experiment data through API |
| B7 | Spring `TelemetryRequest` has no disk/network fields although `disk_samples`/`network_samples` tables exist | Ingest loses disk/network data in Spring path |
| B8 | Simulator registers new clients on every start | Duplicate client records |
| B9 | `server/.env` is present on disk | Must never be committed or printed |
| B10 | Spring Boot `4.1.1` + Java target 21 with local Java 23 | Build/runtime compatibility must be verified |
| B11 | No frontend test/build verification recorded | Unknown current build state |
| B12 | `create_comparison_report.py` hardcodes `testing_records: 290874` and `fedavg_code_modified: False` | Fragile; should read metadata |
| B13 | No unit tests for partition reproducibility | Regressions undetected |
| B14 | Dashboard "Available dataset files" uses hardcoded `data.js` rows | Not driven by inspection report |

## 6. Integration gaps

- Control plane (Spring/Express) vs local client data (CSV + `.npy` indices) is not connected.
- No path from partitions → federated clients → monitoring context → selection decision → experiment record.
- No shared experiment identifier across Python training and PostgreSQL monitoring.
- No export path for experiment results to the dashboard.
- `comparison_report.json` is not served by any API; only static copies are used.

## 7. Dependency status (verified locally)

| Dependency | Status |
|---|---|
| Python | 3.13.6 |
| numpy / pandas / scikit-learn / joblib / psutil | installed |
| torch | 2.10.0 installed |
| flwr (Flower) | **not installed** |
| pytest | 9.0.3 installed |
| Node.js | v22.14.0 |
| Dashboard node_modules | present |
| api/agent/simulator node_modules | **missing** |
| Java | 23.0.2 |
| Maven on PATH | not found; `mvnw` wrapper exists |
| PostgreSQL port 5432 | open |

Because Flower is unavailable and the original implementation is missing, the new FedAvg implementation will be **self-contained PyTorch** with no hard dependency on Flower. This avoids an unverifiable third-party install while matching the documented model, optimiser and aggregation semantics.

## 8. Security concerns

- `server/.env` must stay untracked; server password is injected via `${DB_PASSWORD}`.
- Express CORS is fully open (`cors()` with no origin restriction).
- Client tokens are returned once at registration and stored hashed (good); ensure they are never logged.
- No authentication on Spring `GET /api/clients` (acceptable for local dev, must be documented).
- Raw dataset CSVs must never be sent to the monitoring APIs; this audit confirms current APIs accept only telemetry, not dataset rows.

## 9. Research limitations (current state)

- No federated results → no comparison with the centralized RF baseline.
- Partition report measures class share standard deviation only; it is not a complete non-IID characterisation.
- Simulated clients on one host cannot provide independent hardware energy measurements.
- No real energy metering; any energy statement must be a labelled proxy.
- Historical FedAvg numbers are unverified and must not be used as evidence.

## 10. Recommended implementation order

1. Reusable partitioning + client data loading + validation/tests (preserve existing artifacts).
2. Self-contained PyTorch MLP + FedAvg + metrics + deterministic experiment runner.
3. Context-aware selection design + implementation + unit tests.
4. Run reduced-scale verified experiments; record exact configuration.
5. Add backend read APIs (`/api/dashboard/overview`, experiments, results) and connect dashboard.
6. Literature review + research gap (verified references only).
7. Testing report, sustainability evaluation, final report.

## 11. Preserved invariants

The following must not change without explicit approval:

- `output/splits/train.csv` and `test.csv` (never regenerated for experiments).
- Existing `.npy` partition indices and reports for 5 clients / seed 42 / alpha 0.5.
- `models/greenfed_random_forest.joblib` and `reports/*`.
- Existing Spring Boot and Express API contracts; new endpoints are additive.
- The test split is never used for partitioning, training, or tuning.
