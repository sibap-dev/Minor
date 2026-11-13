# Research Gap

This document states the gap that GreenFed-IDS addresses, the evidence behind it, and the scope of the response. It is deliberately narrow: the project is a reproducible engineering evaluation, not a claim of a new state-of-the-art algorithm.

## 1. Problem statement

Federated intrusion detection for IoT must operate on heterogeneous clients whose computation, memory, disk, network quality, and availability differ, while client data distributions are often non-IID. The literature establishes that:

- FedAvg is communication-intensive and sensitive to non-IID data [1], [2].
- Non-IID skew can substantially reduce accuracy, with severity depending on the partition [3], [4].
- Resource-aware client selection can reduce training time or energy, but reported benefits are workload-dependent [5]–[8].
- FL-IDS is feasible on IoT devices and CICIoT2023 is a relevant public benchmark [9]–[13].
- FL is not automatically sustainable; communication and compute must be accounted for [14], [15].

What remains underexplored is a controlled, same-dataset comparison of **full participation, random selection, resource-aware selection, and multi-factor context-aware selection** on a multi-class IoT intrusion dataset, under both IID and non-IID partitions, with repeated seeds and explicit communication and CPU accounting.

## 2. Gap in detail

### 2.1 Fragmented evaluation

Studies typically vary one axis at a time. A study may compare aggregation rules under non-IID data, or selection policies under a communication budget, or FL-IDS accuracy on a single partition. Few report all of the following in one protocol:

- identical model, features, split, and number of rounds;
- IID and non-IID partitions generated from the same training data;
- multiple random seeds with mean and standard deviation;
- accuracy and macro-F1 on a held-out test set that is never used for training or selection;
- communication volume and CPU time per strategy;
- an explicit accounting of what is measured versus simulated.

Without this, it is difficult to tell whether a reported gain comes from the selection policy, the partition, or an uncontrolled difference in training budget.

### 2.2 Multi-factor context is under-tested

Resource-aware selection often optimizes CPU, memory, or deadline constraints. Context-aware selection can additionally consider network latency and packet loss, data coverage, fairness, and cost. The literature reviews these dimensions [8], but a simple, inspectable scoring function evaluated against random and resource-only baselines on the same data is uncommon. It is also uncommon to report **negative or neutral results** honestly: selection can reduce cost while slightly lowering accuracy, especially under non-IID data.

### 2.3 Sustainability reporting gaps

FL carbon studies show that communication can dominate emissions and that FL can be worse than centralized training in some configurations [14]. Energy/carbon analyses show that learner-population selection can save energy [15]. However, many applied FL-IDS papers report only accuracy and do not report communication or compute. Where cost is reported, the measurement boundary is often unclear. A reproducible accounting of communication megabytes and CPU seconds, with explicit caveats about missing energy meters, is therefore useful even when it is not a full life-cycle assessment.

### 2.4 Dataset-specific evidence

CICIoT2023 is large, recent, and multi-class [11]. Recent FL studies on it compare aggregation rules or normalization methods [12], [13], but do not provide a four-way selection comparison under both IID and Dirichlet non-IID partitions with seed-level variance and cost accounting. This leaves a practical question unanswered for CICIoT2023-style deployments: **what does context-aware selection actually buy, and at what accuracy cost, relative to simpler baselines?**

## 3. Research questions

The project is organized around four questions:

- **RQ1.** Under a fixed model and training budget, how do full participation, random selection, resource-aware selection, and context-aware selection compare on test accuracy and macro-F1 for IID and non-IID partitions?
- **RQ2.** What communication and CPU savings does each selection strategy produce relative to full participation?
- **RQ3.** How variable are the outcomes across random seeds, and does the ranking of strategies change between IID and non-IID settings?
- **RQ4.** What can and cannot be concluded about sustainability from the available measurements?

## 4. Scope of the response

In scope:

- A reproducible PyTorch FedAvg implementation with sample-weighted aggregation.
- IID and Dirichlet (alpha = 0.5) partitions over the existing five-client setup, seed 42.
- Four selection strategies: all clients, random three, resource-aware three, context-aware three.
- Three training seeds (42, 43, 44) per scenario and strategy.
- Held-out test evaluation, macro-F1, communication megabytes, CPU seconds, and training seconds.
- A dashboard that presents the aggregated results and dataset composition without fabricated metrics.
- Documentation of dataset methodology, partitioning, selection design, experiments, sustainability proxies, APIs, testing, and limitations.

Out of scope:

- Real energy or carbon measurement; no power meter or hardware telemetry at the socket level.
- Privacy attacks, secure aggregation, differential privacy, or poisoning defenses.
- Cross-dataset generalization and concept drift.
- Real distributed deployment across independent physical devices.
- A new aggregation algorithm or a claim that context-aware selection is superior.

## 5. Contribution

The contribution is a transparent, reproducible evaluation package:

1. A working FL pipeline on a 34-class IoT intrusion dataset with preserved partitions and a held-out test split.
2. A four-way selection comparison under IID and non-IID data with three seeds and cost accounting.
3. An honest finding: partial participation cut communication by 40% and CPU by roughly 24–47%, while context-aware selection did **not** consistently improve accuracy over random or resource-aware selection and was slightly worse than full participation under non-IID data.
4. An integrated dashboard and documentation set that expose the evidence, including negative results and measurement limits.

## 6. Evidence that the gap is real

- The FL-IDS survey identifies communication overhead, non-IID degradation, and resource constraints as open challenges [9].
- Selection reviews describe heterogeneous objectives and note that gains depend on the setting [8].
- CICIoT2023 provides a large multi-class benchmark [11], and recent FL work on it focuses on aggregation and normalization rather than a four-way selection comparison [12], [13].
- Sustainability studies show that cost accounting changes conclusions and is often incomplete [14], [15].

## 7. What would falsify the project's framing

The framing would be weakened if:

- a controlled rerun showed context-aware selection consistently and significantly outperforming both random and resource-aware selection across seeds and scenarios;
- communication or CPU accounting were shown to be incorrect by more than a small margin;
- the IID and non-IID partitions were shown to leak test data or violate the stated client counts;
- results were found to depend on a coding error rather than the stated protocol.

The current evidence does not support a superiority claim, and the documentation says so explicitly.

## References

[1] H. B. McMahan et al., "Communication-Efficient Learning of Deep Networks from Decentralized Data," AISTATS, 2017. arXiv:1602.05629

[2] P. Kairouz et al., "Advances and Open Problems in Federated Learning," FnT ML, 2021. https://doi.org/10.1561/2200000083

[3] Y. Zhao et al., "Federated Learning with Non-IID Data," arXiv:1806.00582, 2018.

[4] T.-M. H. Hsu, H. Qi, and M. Brown, "Measuring the Effects of Non-Identical Data Distribution for Federated Visual Classification," arXiv:1909.06335, 2019.

[5] T. Nishio and R. Yonetani, "Client Selection for Federated Learning with Heterogeneous Resources in Mobile Edge," IEEE ICC, 2019. https://doi.org/10.1109/ICC.2019.8761315

[6] L. Yu et al., "Jointly Optimizing Client Selection and Resource Management in Wireless Federated Learning for Internet of Things," IEEE IoT-J, 2021. https://doi.org/10.1109/JIOT.2021.3103715

[7] A. Imteaj et al., "A Survey on Federated Learning for Resource-Constrained IoT Devices," IEEE IoT-J, 2021. https://doi.org/10.1109/JIOT.2021.3095077

[8] L. Fu et al., "Client Selection in Federated Learning: Principles, Challenges, and Opportunities," arXiv:2211.01549, 2022.

[9] S. Agrawal et al., "Federated Learning for intrusion detection system: Concepts, challenges and future directions," Computer Communications, 2022. https://doi.org/10.1016/j.comcom.2022.09.012

[10] T. D. Nguyen et al., "DÏoT: A Federated Self-learning Anomaly Detection System for IoT," IEEE ICDCS, 2019. https://doi.org/10.1109/ICDCS.2019.00080

[11] E. C. P. Neto et al., "CICIoT2023: A Real-Time Dataset and Benchmark for Large-Scale Attacks in IoT Environment," Sensors, 2023. https://doi.org/10.3390/s23135941

[12] N. I. Matos Filho et al., "Intrusion Detection in IoT Networks Using Federated Learning," DCOSS-IoT, 2025. https://doi.org/10.1109/DCOSS-IOT65416.2025.00109

[13] P. S. Bouzinis et al., "StatAvg: Mitigating Data Heterogeneity in Federated Learning for Intrusion Detection Systems," IEEE TNSM, 2025. https://doi.org/10.1109/TNSM.2025.3564387

[14] X. Qiu et al., "A first look into the carbon footprint of federated learning," JMLR, 2023. arXiv:2102.07627

[15] S. Savazzi et al., "An Energy and Carbon Footprint Analysis of Distributed and Federated Learning," IEEE TGCN, 2023. https://doi.org/10.1109/TGCN.2022.3186439
