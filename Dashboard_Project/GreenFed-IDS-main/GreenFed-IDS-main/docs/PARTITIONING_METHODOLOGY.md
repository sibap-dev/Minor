# Partitioning Methodology

This document specifies how client partitions were produced and validated. The preserved partitions are used unchanged; no experiment regenerates them.

## 1. Configuration

| Parameter | IID | Non-IID |
|---|---|---:|
| Clients | 5 | 5 |
| Method | Class-proportional IID | Class-wise Dirichlet |
| Seed | 42 | 42 |
| Alpha | n/a | 0.5 |
| Training records | 1,170,022 | 1,170,022 |
| Records assigned | 1,170,022 | 1,170,022 |
| Duplicates | 0 | 0 |
| Empty clients | 0 | 0 |

Only `output/splits/train.csv` is read. The test CSV is never used for partitioning.

## 2. IID algorithm

The implementation is `create_iid_partition` in `federated/greenfed_fl/partitioning.py`:

1. Seed a NumPy generator with `seed=42`.
2. For each of the 34 classes, collect all row indices belonging to that class.
3. Shuffle those indices with the seeded generator.
4. Split the shuffled class indices into five near-equal contiguous chunks with `np.array_split`.
5. Append each client's chunk to that client's index list.
6. Sort each client's final index array.

This is class-proportional IID: every client receives approximately the same number of rows from every class. It does not shuffle the entire dataset once and cut it into five; class-wise allocation gives tighter balance.

Resulting client sizes:

| Client | Rows | Share | Classes present |
|---|---:|---:|---:|
| client_1 | 234,019 | 20.00% | 34 |
| client_2 | 234,012 | 20.00% | 34 |
| client_3 | 234,003 | 20.00% | 34 |
| client_4 | 233,997 | 20.00% | 34 |
| client_5 | 233,991 | 20.00% | 34 |

## 3. Non-IID algorithm

The implementation is `create_dirichlet_partition`:

1. Seed a NumPy generator with `seed=42`.
2. For each of the 34 classes, collect and shuffle that class's row indices.
3. Draw a proportion vector from a symmetric Dirichlet distribution, `Dirichlet(alpha=0.5)` repeated five times.
4. Draw counts with `np.multinomial(n_class_rows, proportions)`.
5. Assign contiguous chunks of the shuffled class indices according to those counts.
6. Sort each client's final index array.

This is a class-wise Dirichlet partition: each class is distributed unevenly across clients, and each client's overall label distribution is therefore skewed. Alpha controls skew; lower alpha produces more concentrated allocations. Alpha = 0.5 is a commonly used middle-to-high heterogeneity setting.

Resulting client sizes:

| Client | Rows | Share | Classes present |
|---|---:|---:|---:|
| client_1 | 220,029 | 18.81% | 34 |
| client_2 | 232,318 | 19.86% | 32 |
| client_3 | 271,630 | 23.22% | 33 |
| client_4 | 325,213 | 27.80% | 32 |
| client_5 | 120,832 | 10.33% | 33 |

The non-IID partition is imbalanced in both rows and labels. Some client/class counts are very small (for example, single-digit counts for several rare classes on some clients), while dominant DDoS classes are concentrated on particular clients.

## 4. Validation

`validate_partition` checks the following for each scenario:

- `total_training_records`: expected 1,170,022.
- `records_assigned`: 1,170,022.
- `unique_indices`: 1,170,022.
- `duplicate_indices_across_clients`: 0.
- `per_client_duplicates`: empty.
- `indices_in_valid_range`: true; every index is in `[0, 1,170,022)`.
- `all_records_assigned_once`: true; the sorted union equals `arange(1,170,022)`.
- `empty_clients`: none.
- `test_split_used`: false.

The validation report is stored at `federated/results/partition_validation.json` and copied to the dashboard as `public/data/experiments/partition_validation.json`.

Both scenarios also record `report_matches_recomputed_indices: true`, meaning the saved `.npy` index files agree with the class distributions in the saved reports. No report mismatches were found.

## 5. Heterogeneity measure

`class_share_std` measures how unevenly each class is spread across clients. For every class:

1. Take the count assigned to each of the five clients.
2. Convert counts to percentages of that class's total.
3. Compute the sample standard deviation (`ddof=1`) of those five percentages.
4. Average the per-class standard deviations over all classes.

The result is in percentage points.

| Scenario | Class-share std |
|---|---:|
| IID | 0.1613 pp |
| Non-IID | 21.2734 pp |

The IID value is near zero, as expected for class-proportional allocation. The non-IID value is about 132 times larger, confirming substantial label skew. This metric is descriptive; it is not a formal divergence measure and is not used as an optimization target.

The value depends on the standard-deviation convention. The implementation uses sample standard deviation (`ddof=1`), and the reported numbers use that definition. Changing to population standard deviation (`ddof=0`) would produce smaller values, so the metric must always be reported together with its definition.

## 6. Why these partitions

- Five clients keep full experiments tractable on a single host while still exercising partial participation (three of five selected).
- IID provides a low-heterogeneity reference.
- Dirichlet alpha = 0.5 provides substantial but not pathological label skew. Every client still has 32–34 classes, so the setting tests realistic imbalance rather than the extreme one-class-per-client case used in some non-IID papers [1].
- A single partition seed (42) is used for both scenarios so the training-row assignment is deterministic. Training seeds vary separately (42, 43, 44), isolating training randomness from partition randomness.

## 7. Limitations

- The non-IID partition is simulated with Dirichlet, not derived from real device or network provenance. Real IoT deployments may have different skew patterns.
- Only one partition seed is used. Partition-level variance is not estimated; the reported standard deviations are across training seeds.
- Five clients is small. Results may not scale to dozens or hundreds of clients.
- All clients share the same 39-feature schema and the same host environment, so feature heterogeneity and hardware heterogeneity are not represented.
- The preserved partitions were generated by a script in `scripts/partitioning/partition_dataset.py`; the federated package includes an independent implementation used for validation and repartitioning. The preserved `.npy` files are treated as the source of truth.

## 8. Reproduction

```powershell
python federated/validate_partitions.py --methods iid,non_iid
```

This reads the preserved partitions, recomputes validation, and writes `federated/results/partition_validation.json`. To generate new partitions into a separate directory without touching the preserved files:

```powershell
python federated/repartition.py --method non_iid --alpha 0.5 --seed 42 --output <new-dir>
```

## References

[1] Y. Zhao, M. Li, L. Lai, N. Suda, D. Civin, and V. Chandra, "Federated Learning with Non-IID Data," arXiv:1806.00582, 2018.
