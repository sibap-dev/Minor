# Dataset Methodology

This document records what is known about the dataset actually used, how it was verified, and which claims cannot be made because the original split-generation code is not present.

## 1. Provenance

The project uses a pre-existing feature-extracted CSV split derived from CICIoT2023 (Neto et al., *Sensors*, 2023). CICIoT2023 was generated from 33 attacks against a topology of 105 IoT devices and covers seven attack categories plus benign traffic [1]. The raw PCAP files are not part of this repository and were not reprocessed here.

The split files are:

| File | Rows | Columns | Features | Label | Classes |
|---|---:|---:|---:|---|---:|
| `output/splits/train.csv` | 1,170,022 | 40 | 39 | `Label` | 34 |
| `output/splits/test.csv` | 290,874 | 40 | 39 | `Label` | 34 |

The files were inherited from the earlier project state. The exact code that produced this split was not available, so this document does **not** claim a specific stratification procedure. What was verified is listed below.

## 2. Verified properties

Verification was performed by reading both CSVs and the packaged dataset report:

- 40 columns in each file: 39 numeric features and one string label column named `Label`.
- 34 distinct label values in each file.
- Zero missing values in every column in both files.
- All 39 feature columns are numeric (`float64` or `int64`); `Label` is `object`.
- The test set contains all 34 classes.
- Row counts match the packaged `dataset_report.json` served by `/api/datasets/summary`.
- The test split is never read during partitioning or training. It is loaded only after training for final evaluation.

Verification commands used:

```powershell
python -c "import pandas as pd; d=pd.read_csv('output/splits/train.csv'); print(d.shape, d['Label'].nunique(), d.isna().sum().sum())"
python -c "import pandas as pd; d=pd.read_csv('output/splits/test.csv'); print(d.shape, d['Label'].nunique(), d.isna().sum().sum())"
```

## 3. Features

The 39 features are the columns present in the prepared CSV, in file order:

`Header_Length`, `Protocol Type`, `Time_To_Live`, `Rate`, `fin_flag_number`, `syn_flag_number`, `rst_flag_number`, `psh_flag_number`, `ack_flag_number`, `ece_flag_number`, `cwr_flag_number`, `ack_count`, `syn_count`, `fin_count`, `rst_count`, `HTTP`, `HTTPS`, `DNS`, `Telnet`, `SMTP`, `SSH`, `IRC`, `TCP`, `UDP`, `DHCP`, `ARP`, `ICMP`, `IGMP`, `IPv`, `LLC`, `Tot sum`, `Min`, `Max`, `AVG`, `Std`, `Tot size`, `IAT`, `Number`, `Variance`.

These are flow-level statistics and protocol indicators. The model treats them as numeric inputs without re-engineering. Several features are aggregate statistics over a flow, so they are not independent packet-header fields. This matters for interpretation: a high score does not by itself demonstrate deployability on raw packet streams.

## 4. Class distribution

The training set is strongly long-tailed. The largest classes are DDoS flood variants; BENIGN is mid-sized; several web and reconnaissance classes are very rare.

Top training classes:

| Class | Rows | Training share |
|---|---:|---:|
| DDOS-ICMP_FLOOD | 179,201 | 15.32% |
| DDOS-UDP_FLOOD | 134,513 | 11.50% |
| DDOS-TCP_FLOOD | 111,587 | 9.54% |
| DDOS-PSHACK_FLOOD | 102,130 | 8.73% |
| DDOS-SYN_FLOOD | 101,429 | 8.67% |
| DDOS-RSTFINFLOOD | 99,989 | 8.55% |
| DDOS-SYNONYMOUSIP_FLOOD | 89,958 | 7.69% |
| DOS-UDP_FLOOD | 82,456 | 7.05% |
| DOS-TCP_FLOOD | 66,769 | 5.71% |
| DOS-SYN_FLOOD | 50,391 | 4.31% |
| BENIGN | 27,345 | 2.34% |

Rare training classes (below 1% of training rows):

| Class | Rows | Training share |
|---|---:|---:|
| UPLOADING_ATTACK | 33 | 0.0028% |
| RECON-PINGSWEEP | 42 | 0.0036% |
| BACKDOOR_MALWARE | 77 | 0.0066% |
| XSS | 109 | 0.0093% |
| SQLINJECTION | 122 | 0.0104% |
| COMMANDINJECTION | 137 | 0.0117% |
| BROWSERHIJACKING | 146 | 0.0125% |
| DICTIONARYBRUTEFORCE | 330 | 0.0282% |
| DDOS-SLOWLORIS | 584 | 0.0499% |
| DDOS-HTTP_FLOOD | 754 | 0.0644% |
| DOS-HTTP_FLOOD | 1,880 | 0.1607% |
| RECON-PORTSCAN | 2,108 | 0.1802% |
| RECON-OSSCAN | 2,357 | 0.2014% |
| RECON-HOSTDISCOVERY | 3,351 | 0.2864% |
| DNS_SPOOFING | 4,512 | 0.3856% |

The test set has the same 34 classes but different counts; rare classes remain rare (for example, UPLOADING_ATTACK has 6 test rows, RECON-PINGSWEEP has 13, BACKDOOR_MALWARE has 14).

Consequence: overall accuracy is dominated by DDoS classes. Macro-F1 is therefore reported as a primary metric because it weights each class equally. Even so, macro-F1 is noisy when a class has only a handful of test examples.

## 5. Preprocessing used in the federated pipeline

The federated package applies the following steps, all fit on training data only:

1. Read the training CSV and separate `Label` from the 39 features.
2. Encode labels with a mapping built from the training labels.
3. Partition the training rows into clients using the preserved partition indices.
4. Hold out a validation subset from each client's training rows for round-level monitoring. The validation split is drawn from training data only; the test CSV is not touched.
5. Fit feature scaling on the training data used for the run and apply it to validation and test data.
6. Optionally compute class weights for balanced loss. The recorded full runs use `class_weight_mode=none` unless a run metadata file says otherwise.
7. Train the MLP with cross-entropy loss and evaluate on the held-out test set after the final round.

The test set is not used for early stopping, hyperparameter selection, or client selection.

## 6. What the dataset supports and does not support

Supported claims:

- Multi-class classification over 34 CICIoT2023-derived labels.
- Comparison of IID and Dirichlet non-IID partitions drawn from the same training rows.
- Accuracy and macro-F1 on a fixed held-out test set.
- Class-imbalance discussion grounded in actual counts.

Unsupported claims:

- Temporal generalization or concept-drift robustness. The split is a static row split, and the original split code is unavailable, so temporal ordering is not guaranteed.
- Raw-packet deployability. Features are flow-level aggregates, and the model consumes the CSV representation, not live packets.
- Exact reproduction of CICIoT2023 benchmark numbers from the original paper. The feature set, split, and model differ.
- Causal claims about attack behavior. The model learns associations in the prepared features.
- Privacy guarantees. Federated training keeps rows local in this simulation, but no differential privacy or secure aggregation is used.

## 7. Reproduction and integrity

- The CSVs are treated as immutable. No experiment writes to `output/splits/`.
- Partition validation confirms that every training row is assigned exactly once, with no duplicates and no indices outside the training range.
- The test split is loaded only after training for the final evaluation.
- Checksums of the CSV files are not stored in the repository, so byte-level integrity is not independently attested. The row/column/label counts above are the recorded verification.

## References

[1] E. C. P. Neto, S. Dadkhah, R. Ferreira, A. Zohourian, R. Lu, and A. A. Ghorbani, "CICIoT2023: A Real-Time Dataset and Benchmark for Large-Scale Attacks in IoT Environment," *Sensors*, 23(13):5941, 2023. https://doi.org/10.3390/s23135941
