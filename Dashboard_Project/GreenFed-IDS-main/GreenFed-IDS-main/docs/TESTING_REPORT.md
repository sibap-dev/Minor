# Testing Report

Verified: 2026-11-12

This report records the tests that exist, the commands used, the observed results, and the gaps. It distinguishes automated tests from manual verification and does not claim coverage that was not measured.

## 1. Summary

| Suite | Command | Result |
|---|---|---|
| Python federated package | `python -m pytest -q` | **37 passed** in 16.55 s |
| Spring Boot backend | `.\mvnw.cmd test -q` with `DB_PASSWORD` set | **3 passed**, 0 failures, 0 errors |
| Dashboard production build | `npm run build` | **Success**, 2,052 modules, 669.27 kB JS / 193.64 kB gzip |
| Partition validation | `python federated/validate_partitions.py` | Both scenarios valid; 1,170,022 records, 0 duplicates |
| Experiment aggregation | `python federated/aggregate_results.py --tag full` | Regenerated JSON/CSV/MD for 8 scenario/strategy groups |

## 2. Python tests

Location: `federated/tests/`

| File | Focus |
|---|---|
| `conftest.py` | Shared fixtures and import path setup |
| `test_context_metrics.py` | Context validation, provenance, simulated profile generation, metric helpers |
| `test_fedavg.py` | Model construction, local training, aggregation, evaluation, resource accounting |
| `test_partitioning.py` | IID and Dirichlet partitioning, exact coverage, no duplicates, report generation |
| `test_real_artifacts.py` | Preserved partitions, reports, and aggregate artifacts are consistent |
| `test_selection.py` | Eligibility, normalization, scoring, ranking, random/full participation, tie-breaking, participation counters |

Command:

```powershell
cd federated
python -m pytest -q
```

Observed:

```
.....................................                                    [100%]
37 passed in 16.55s
```

What is covered:

- Index coverage and duplicate rejection for both partition methods.
- Deterministic behavior with fixed seeds.
- Context range validation, provenance enum, and simulated profile counts derived from real partition reports.
- Eligibility constraints and relaxed-selection behavior.
- Ranking determinism and strategy rejection for unknown names.
- Sample-weighted aggregation and model state size.
- Communication accounting formula.
- Reading the preserved artifacts and checking aggregate consistency.

What is not covered:

- Full two-round training on the real 1.17M-row dataset (too slow for unit tests).
- Numerical accuracy thresholds for a trained model.
- GPU paths (none are implemented).
- Energy measurement (none exists).

## 3. Spring Boot tests

Location: `server/src/test/java/`

| Test | Focus |
|---|---|
| `ServerApplicationTests` | Application context loads with Flyway and JPA |
| `DashboardApiTests#overviewReturnsAggregates` | `GET /api/dashboard/overview` returns numeric aggregates and a source field |
| `DashboardApiTests#clientsReturnsAnArray` | `GET /api/dashboard/clients` returns an array with expected keys |

Command:

```powershell
$line = Get-Content .env | Where-Object { $_ -match '^\s*DB_PASSWORD=' } | Select-Object -First 1
$env:DB_PASSWORD = ($line -replace '^\s*DB_PASSWORD=','').Trim().Trim('"')
.\mvnw.cmd test -q
```

Observed from Surefire reports:

```
Tests run: 2, Failures: 0, Errors: 0, Skipped: 0 -- DashboardApiTests
Tests run: 1, Failures: 0, Errors: 0, Skipped: 0 -- ServerApplicationTests
```

Important: these are **integration tests against the real PostgreSQL database**, not an in-memory substitute. If `DB_PASSWORD` is unset or wrong, Flyway fails with `FATAL: password authentication failed for user "postgres"` and all three tests error. A run without the password produced exactly that failure. The tests pass when the `.env` password is loaded into the environment.

Design notes:

- Spring Boot 4.1.1 does not provide `TestRestTemplate`; the tests use `@SpringBootTest(webEnvironment = RANDOM_PORT)`, `@LocalServerPort`, Java's `HttpClient`, and a manually constructed Jackson `ObjectMapper`.
- `@AutoConfigureMockMvc` is not on the test classpath.
- There is no `ObjectMapper` bean because the project uses Jackson 3 on the application classpath and constructs Jackson 2 `ObjectMapper` manually in tests.

What is not covered:

- Client registration, heartbeat, and telemetry endpoints.
- Authentication failure paths and token revocation.
- Validation errors and 4xx responses.
- Concurrency and transaction rollback.
- Flyway migration upgrade from an older schema.

## 4. Dashboard build

Command:

```powershell
cd client/greenfed-dashboard-download
npm run build
```

Observed:

```
✓ 2052 modules transformed.
dist/index.html                 0.55 kB │ gzip: 0.33 kB
dist/assets/index-Bkv4EOCm.css 16.33 kB │ gzip: 4.26 kB
dist/assets/index-6WzjC-5u.js 669.27 kB │ gzip: 193.64 kB
✓ built in 6.90s
```

There is a chunk-size warning above 500 kB. It is a warning, not a failure. The bundle is large because it includes the charting and icon libraries; no code splitting is configured.

What is not covered:

- No unit tests for React components.
- No browser end-to-end tests.
- No accessibility audit.
- No visual regression tests.
- No test that the dashboard handles a down backend beyond manual inspection.

## 5. Manual verification performed

- Confirmed dataset row counts, 34 labels, zero missing values, and 39 numeric features from both CSVs.
- Confirmed preserved partitions cover all 1,170,022 training rows exactly once with no duplicates and no test rows.
- Confirmed the IID and non-IID class-share standard deviations (0.1613 and 21.2734 percentage points).
- Confirmed the aggregate tables regenerate from run directories and match the recorded numbers.
- Confirmed the dashboard production build succeeds and copies the experiment artifacts into `public/data/experiments/`.
- Confirmed the Spring dashboard endpoints return live aggregates against PostgreSQL.

## 6. Reproducibility caveats

- Tests depend on the local environment: Python 3.13 with PyTorch, and PostgreSQL 18 with the `greenfed_monitor` database.
- The Spring tests are not hermetic. A CI pipeline would need a provisioned database or a test profile with an isolated schema.
- There are no pinned lockfiles for Python dependencies in the repository root; the environment is described in the README, not enforced by a lock.
- No lint or type-check step is configured for the Python package, Spring service, or React app. `npm run build` is the only frontend check.
- Test runtimes depend on hardware; the recorded times are from this machine, not guarantees.

## 7. Recommended next tests

1. Spring: registration → heartbeat → telemetry happy path, with a temporary schema or Testcontainers.
2. Spring: 401/400 paths and revoked/expired token handling.
3. Python: a single-round smoke test on a small CSV fixture to catch integration regressions without the full dataset.
4. Python: assertion that selection scores match hand-computed values for a fixed five-client context.
5. Frontend: a smoke test that each page renders with static data and shows an offline state when fetch fails.
6. End-to-end: agent payload → Express ingest → Spring dashboard aggregate.

These are recommendations, not completed work.
