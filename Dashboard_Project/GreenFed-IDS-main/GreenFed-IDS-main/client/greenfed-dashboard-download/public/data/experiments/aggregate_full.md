# Aggregated experiments (full)

Mean and sample std over independent random seeds. Held-out test set is never used for training or selection.

| Scenario | Strategy | Runs | Test accuracy | Test macro-F1 | Comm. MB | CPU s |
|---|---|---:|---:|---:|---:|---:|
| iid | all | 3 | 0.7531 and 0.0014 | 0.4772 and 0.0034 | 1.189 and 0.000 | 37.04 and 1.46 |
| iid | context | 3 | 0.7529 and 0.0005 | 0.4767 and 0.0037 | 0.713 and 0.000 | 28.08 and 7.71 |
| iid | random | 3 | 0.7536 and 0.0019 | 0.4738 and 0.0010 | 0.713 and 0.000 | 24.34 and 2.20 |
| iid | resource | 3 | 0.7558 and 0.0055 | 0.4824 and 0.0122 | 0.713 and 0.000 | 27.97 and 6.85 |
| non_iid | all | 3 | 0.7256 and 0.0031 | 0.4188 and 0.0034 | 1.189 and 0.000 | 47.50 and 8.44 |
| non_iid | context | 3 | 0.7069 and 0.0108 | 0.3899 and 0.0115 | 0.713 and 0.000 | 27.01 and 5.15 |
| non_iid | random | 3 | 0.7118 and 0.0256 | 0.4122 and 0.0066 | 0.713 and 0.000 | 28.23 and 9.17 |
| non_iid | resource | 3 | 0.7072 and 0.0107 | 0.3889 and 0.0082 | 0.713 and 0.000 | 25.33 and 5.77 |

## Efficiency relative to full-participation FedAvg

| Scenario | Strategy | Delta accuracy (pp) | Comm. reduction | CPU reduction |
|---|---|---:|---:|---:|
| iid | all | +0.00 | 0.0% | 0.0% |
| iid | context | -0.02 | 40.0% | 24.2% |
| iid | random | +0.05 | 40.0% | 34.3% |
| iid | resource | +0.27 | 40.0% | 24.5% |
| non_iid | all | +0.00 | 0.0% | 0.0% |
| non_iid | context | -1.87 | 40.0% | 43.1% |
| non_iid | random | -1.37 | 40.0% | 40.6% |
| non_iid | resource | -1.84 | 40.0% | 46.7% |
