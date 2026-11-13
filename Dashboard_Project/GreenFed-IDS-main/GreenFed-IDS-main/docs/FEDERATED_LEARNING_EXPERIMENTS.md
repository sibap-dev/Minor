# Federated Learning Experiments

This document records the protocol and results of the full experiment matrix. All values come from `federated/results/aggregate_full.json`, `aggregate_full.csv`, and the per-run directories. No result is hand-entered from an external source.

## 1. Objective

Compare four participation strategies under IID and non-IID client partitions on the same model, data, and training budget:

- `all`: full participation (all five clients every round), conventional FedAvg.
- `random`: uniform random selection of three clients.
- `resource`: resource-aware selection of three clients.
- `context`: multi-factor context-aware selection of three clients.

Primary metrics: held-out test accuracy and macro-F1. Secondary metrics: communication megabytes and CPU seconds.

## 2. Protocol

| Item | Value |
|---|---|
| Training data | `output/splits/train.csv`, 1,170,022 rows |
| Test data | `output/splits/test.csv`, 290,874 rows |
| Partitions | Preserved IID and Dirichlet alpha = 0.5, seed 42, 5 clients |
| Model | MLP 39 -> 128 -> 64 -> 34, ReLU |
| Parameters | 15,586 |
| Model state size | 62,344 bytes |
| Optimizer | Adam |
| Learning rate | 0.001 |
| Batch size | 256 |
| Local epochs | 1 |
| Rounds | 2 |
| Aggregation | Sample-weighted FedAvg |
| Clients per round | 5 for `all`, 3 for the other strategies |
| Class weighting | `none` for the recorded full runs |
| Training seeds | 42, 43, 44 |
| Validation | 10% split from each client's training rows |
| Test use | Final evaluation only; never used for training, validation, or selection |
| Context | Simulated profiles, seed 42, provenance recorded |
| Threads | 4 |

Each run trains all four strategies in sequence with the same data preparation and random seed. A run directory holds `run_metadata.json`, `summary.json`, and per-strategy `results.json` and `rounds.csv`.

## 3. Runs

| Scenario | Seed | Run directory |
|---|---:|---|
| IID | 42 | `20261112_155106_iid_s42_full` |
| Non-IID | 42 | `20261112_155157_non_iid_s42_full` |
| IID | 43 | `20261112_155246_iid_s43_full` |
| Non-IID | 43 | `20261112_155336_non_iid_s43_full` |
| IID | 44 | `20261112_155427_iid_s44_full` |
| Non-IID | 44 | `20261112_155512_non_iid_s44_full` |

Aggregation uses the tag `full`:

```powershell
python federated/aggregate_results.py --tag full
```

## 4. Results

Mean and sample standard deviation across the three training seeds. Cells show `mean and std`.

| Scenario | Strategy | Runs | Test accuracy | Test macro-F1 | Comm. MB | CPU s |
|---|---|---:|---:|---:|---:|---:|
| IID | all | 3 | 0.7531 and 0.0014 | 0.4772 and 0.0034 | 1.189 and 0.000 | 37.04 and 1.46 |
| IID | random | 3 | 0.7536 and 0.0019 | 0.4738 and 0.0010 | 0.713 and 0.000 | 24.34 and 2.20 |
| IID | resource | 3 | 0.7558 and 0.0055 | 0.4824 and 0.0122 | 0.713 and 0.000 | 27.97 and 6.85 |
| IID | context | 3 | 0.7529 and 0.0005 | 0.4767 and 0.0037 | 0.713 and 0.000 | 28.08 and 7.71 |
| Non-IID | all | 3 | 0.7256 and 0.0031 | 0.4188 and 0.0034 | 1.189 and 0.000 | 47.50 and 8.44 |
| Non-IID | random | 3 | 0.7118 and 0.0256 | 0.4122 and 0.0066 | 0.713 and 0.000 | 28.23 and 9.17 |
| Non-IID | resource | 3 | 0.7072 and 0.0107 | 0.3889 and 0.0082 | 0.713 and 0.000 | 25.33 and 5.77 |
| Non-IID | context | 3 | 0.7069 and 0.0108 | 0.3899 and 0.0115 | 0.713 and 0.000 | 27.01 and 5.15 |

Efficiency relative to full participation:

| Scenario | Strategy | Delta accuracy (pp) | Communication reduction | CPU reduction |
|---|---|---:|---:|---:|
| IID | all | +0.00 | 0.0% | 0.0% |
| IID | random | +0.05 | 40.0% | 34.3% |
| IID | resource | +0.27 | 40.0% | 24.5% |
| IID | context | -0.02 | 40.0% | 24.2% |
| Non-IID | all | +0.00 | 0.0% | 0.0% |
| Non-IID | random | -1.37 | 40.0% | 40.6% |
| Non-IID | resource | -1.84 | 40.0% | 46.7% |
| Non-IID | context | -1.87 | 40.0% | 43.1% |

Communication is identical for the three partial strategies because each round transfers the model state to and from exactly three clients, and the state size is fixed: `62,344 bytes * 2 * 3 * 2 rounds = 748,128 bytes = 0.713 MB`. Full participation transfers `62,344 * 2 * 5 * 2 = 1,246,880 bytes = 1.189 MB`. The 40% reduction is therefore structural, not an empirical accident. CPU varies because client data sizes and thread scheduling differ.

## 5. Interpretation

### 5.1 Non-IID degrades all strategies

Full participation drops from 0.7531 (IID) to 0.7256 (Non-IID), a 2.75 percentage-point accuracy loss, and macro-F1 drops from 0.4772 to 0.4188. This is consistent with the non-IID literature and with the much larger class-share standard deviation in the non-IID partition.

### 5.2 Partial participation costs accuracy under non-IID

Under IID, the three partial strategies are statistically indistinguishable from full participation on accuracy (differences within 0.27 pp, with standard deviations of similar size). Under non-IID, every partial strategy is 1.37–1.87 pp below full participation. With only two rounds, clients that are not selected contribute no updates, and skew means a selected subset may not represent the global label distribution.

### 5.3 Context-aware selection did not win

Context-aware selection:

- was 0.02 pp below full participation on IID (essentially neutral);
- was 1.87 pp below full participation on non-IID;
- was 0.07 pp below random on IID and 0.49 pp below random on non-IID;
- was 0.29 pp below resource-aware on IID and 0.03 pp below resource-aware on non-IID.

The differences among partial strategies are small relative to seed variance, especially under non-IID (random std 0.0256). The experiment does **not** support a claim that context-aware selection is more accurate than random or resource-aware selection. It supports a narrower claim: at `k = 3` of 5 clients, partial participation halves communication and reduces CPU, and the accuracy cost is small under IID but not negligible under non-IID.

### 5.4 Resource-aware selection was not consistently best either

Resource-aware selection has the highest mean IID accuracy (0.7558) and the highest IID macro-F1 (0.4824), but the highest standard deviations (0.0055 accuracy, 0.0122 macro-F1). Under non-IID it has the lowest mean accuracy (0.7072) and lowest macro-F1 (0.3889). Ranking by mean alone would overstate the evidence; seed variance and scenario matter.

### 5.5 Macro-F1 is much lower than accuracy

Accuracy is around 0.71–0.76, but macro-F1 is around 0.39–0.48. The model is strong on dominant DDoS classes and weak on rare classes. This is expected for a 34-class long-tailed dataset with a small MLP trained for two rounds.

### 5.6 Relationship to the centralized baseline

The preserved centralized Random Forest reports test accuracy 0.7605 and macro-F1 0.5711 on the same test split. The federated MLP reaches similar accuracy after only two rounds (0.7531 IID full) but much lower macro-F1. This is not a controlled comparison: the models, training budgets, and optimization methods differ. It is a sanity reference, not evidence that FL matches the centralized baseline.

## 6. Threats to validity

- **Two rounds, one local epoch**: results reflect a short budget, not convergence. Rankings may change with more rounds.
- **Three seeds**: standard deviations are descriptive, not confidence intervals. Non-IID random has a large std, so mean differences below ~2 pp should be treated cautiously.
- **One partition seed**: partition-level variance is not estimated.
- **Simulated context**: selection uses generated resource values, not independent device measurements.
- **Single host**: simulated clients share CPU, memory, and disk, so wall-clock and CPU measurements are not independent per-client measurements.
- **No class weighting**: rare-class performance is poor. Balanced loss was implemented but not used in the recorded full runs.
- **No hyperparameter search**: learning rate, batch size, and architecture were fixed before the full runs.
- **Test set reuse**: the test set is fixed and was used for final reporting across runs. It was not used for tuning, but repeated reporting on one split can overfit the narrative.
- **No privacy or adversarial evaluation**: results do not cover poisoning, inference attacks, or secure aggregation.

## 7. Reproducibility

```powershell
python federated/validate_partitions.py --methods iid,non_iid
python federated/generate_context.py --scenario iid --seed 42
python federated/run_experiment.py --scenario iid --strategy all-strategies --seed 42 --rounds 2 --tag full
python federated/run_experiment.py --scenario non_iid --strategy all-strategies --seed 42 --rounds 2 --tag full
python federated/aggregate_results.py --tag full
```

To reproduce all six runs, repeat for seeds 42, 43, and 44 and both scenarios. Runtime depends on hardware; the recorded CPU totals are host-process measurements, not device-level energy.

## 8. Artifacts

- `federated/results/aggregate_full.json`: machine-readable aggregate.
- `federated/results/aggregate_full.csv`: flat table.
- `federated/results/aggregate_full.md`: human-readable tables.
- `federated/results/<run_id>/run_metadata.json`: configuration and provenance.
- `federated/results/<run_id>/summary.json`: four strategy summaries per run.
- `federated/results/<run_id>/<strategy>/results.json`: rounds, selections, metrics, resource summary.
- `federated/results/<run_id>/<strategy>/rounds.csv`: per-round metrics.
- Dashboard copies under `client/greenfed-dashboard-download/public/data/experiments/`.
