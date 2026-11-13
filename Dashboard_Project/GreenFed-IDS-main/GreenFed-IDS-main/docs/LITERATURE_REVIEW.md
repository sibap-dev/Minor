# Literature Review

Reviewed: 2026-11-12

This review covers the literature needed to position GreenFed-IDS: federated learning (FL) foundations, statistical heterogeneity, client selection under resource constraints, FL for IoT intrusion detection, the CICIoT2023 dataset, and sustainability analysis. Metadata and claims below were checked against the publisher or arXiv abstract pages listed in the references. This is a focused engineering review, not a systematic review or meta-analysis; no result is attributed to a paper unless it appears in that paper's abstract or publisher summary.

## 1. Federated learning foundations

Federated learning trains a shared model across clients while keeping raw data local. McMahan et al. introduced Federated Averaging (FedAvg), which combines local stochastic gradient descent with server-side model averaging and is robust to unbalanced and non-IID client data. Their experiments reported a 10–100x reduction in communication rounds compared with synchronized SGD, establishing communication as a first-class constraint [1].

Kairouz et al. frame FL as a setting where multiple clients collaborate under a central server without exchanging raw data. They distinguish cross-device and cross-silo settings and enumerate open problems in systems, privacy, security, fairness, and optimization [2]. Bonawitz et al. describe a production FL system for mobile devices and highlight device availability, unreliable connectivity, interrupted execution, and limited on-device resources as practical design constraints [3]. These system-level concerns motivate explicit client selection rather than assuming every client can participate in every round.

## 2. Statistical heterogeneity and non-IID data

Non-IID client data is a defining FL challenge. Zhao et al. showed that FedAvg accuracy can fall by up to about 55% for highly skewed non-IID partitions where each client holds a single class, and linked the degradation to weight divergence measured with earth mover's distance. Sharing a small globally held subset (5%) improved CIFAR-10 accuracy by about 30% in their experiments [4]. Hsu et al. proposed Dirichlet sampling to synthesize a continuous range of client similarity. Performance degraded as client distributions became more dissimilar, and server momentum (FedAvgM) improved the most skewed CIFAR-10 setting from 30.1% to 76.9% [5]. Together, these results justify evaluating both IID and Dirichlet-based non-IID partitions and reporting variance across seeds.

## 3. Client selection and resource constraints

Random client selection is simple but ignores heterogeneous computation, bandwidth, and availability. Nishio and Yonetani proposed FedCS, which selects clients under resource constraints to aggregate as many updates as possible within a deadline and shortens training time relative to the original FL protocol [6]. Yu et al. formulated joint client selection and resource management for wireless FL and proposed ELASTIC, which trades the number of selected clients against total client energy by allocating CPU frequency and transmission power [7]. Imteaj et al. survey FL for resource-constrained IoT devices and identify limited processing, bandwidth, power, and storage as core obstacles [8].

Fu et al. organize the client-selection literature around heterogeneity in data and hardware, noting that random sampling can reduce accuracy, slow convergence, and degrade fairness; they review selection principles and open opportunities [9]. This body of work supports selection strategies that combine resource headroom, network quality, data coverage, fairness, and cost. It also cautions that gains are workload- and deployment-dependent.

## 4. FL for IoT intrusion detection

Agrawal et al. survey FL for intrusion detection systems (IDS). They describe the local-update/global-aggregation loop, review FL-IDS applications, and list challenges including communication overhead, poisoning, high false alarms under non-IID data, and resource management on low-power IoT devices [10]. Nguyen et al. presented DÏoT, described as the first system to apply FL to anomaly-detection-based intrusion detection for IoT. Evaluated on more than 30 off-the-shelf IoT devices, DÏoT reported a 95.6% detection rate, about 257 ms detection time, and no false alarms in a real smart-home deployment [11]. These results show that FL-IDS is feasible in principle, while the survey highlights that efficiency and heterogeneity remain open engineering problems.

## 5. CICIoT2023 and recent FL-IDS evidence

Neto et al. introduced CICIoT2023, generated from 33 attacks executed on a topology of 105 IoT devices and grouped into seven attack categories (DDoS, DoS, Recon, Web-based, brute force, spoofing, and Mirai). The dataset is distributed as PCAP and feature-extracted CSV, and the paper benchmarks machine-learning detectors [12]. This project uses the previously prepared 39-feature CSV split derived from that dataset.

Recent work applies FL to CICIoT2023. Matos Filho et al. compared FedAvg, FedProx, and FedAdam with a 1D-CNN under different partitions and found FedProx more stable under data heterogeneity, FedAvg sensitive to non-uniform distributions, and FedAdam inconsistent on more complex tasks [13]. Bouzinis et al. proposed StatAvg, which shares per-client feature means and variances for universal normalization, and reported 4–17% IDS accuracy gains on TON-IoT and CIC-IoT-2023 relative to normalization baselines [14]. A multi-dataset evaluation by Bilal et al. benchmarked FedAvg, FedProx, and FedNova with LSTM and Transformer backbones; in-domain accuracy was in the 92–98% range, cross-dataset macro-F1 dropped by up to 30 percentage points, and FedNova reduced communication by roughly 15–25% relative to FedAvg [15]. These studies reinforce that aggregation and heterogeneity handling materially affect FL-IDS outcomes, and that cross-environment generalization is difficult.

## 6. Sustainability and green FL

FL is not automatically greener than centralized training. Qiu et al. proposed a carbon-footprint model and found that, depending on configuration, FL can emit up to two orders of magnitude more carbon than centralized learning; communication can range from 0.4% to more than 95% of total emissions, and more efficient strategies reduced emissions by up to 60% in their study [16]. Savazzi et al. developed an energy and carbon analysis for distributed and federated learning and reported that selecting the learner population can save roughly 20–30% or more per round relative to baselines in their case studies [17]. These findings motivate measuring communication volume and compute time, reporting them as proxies when direct energy measurement is unavailable, and avoiding blanket claims that FL is sustainable.

## 7. Synthesis

Established findings:

- FedAvg is a practical baseline, but communication and client heterogeneity are central constraints [1]–[3].
- Non-IID data can substantially degrade accuracy, and the severity depends on skew [4], [5].
- Resource-aware client selection can reduce training time or energy, but reported gains depend on assumptions and workloads [6]–[9].
- FL-IDS on IoT is feasible and has been demonstrated on real devices and public datasets [10]–[15].
- FL sustainability must be measured; it is not guaranteed by decentralization [16], [17].

Contested or context-dependent findings:

- Whether selection improves accuracy versus only efficiency depends on the strategy, data distribution, and number of rounds [6], [7], [9].
- The best aggregation rule under non-IID IDS data varies across studies; FedProx, FedNova, and normalization-based methods each show benefits in different settings [13]–[15].

Gaps relevant to this project:

- Few studies jointly compare full participation, random, resource-aware, and context-aware selection on the same 34-class IoT attack dataset under both IID and non-IID partitions while reporting communication and CPU cost.
- Context-aware selection that combines resource, network, data coverage, fairness, and cost is underexplored for CICIoT2023-style multi-class IDS.
- Sustainability reporting often omits measured or computed communication/compute proxies, and real energy measurement is rare.

## References

[1] H. B. McMahan, E. Moore, D. Ramage, S. Hampson, and B. Agüera y Arcas, "Communication-Efficient Learning of Deep Networks from Decentralized Data," *AISTATS*, PMLR 54:1273–1282, 2017. https://proceedings.mlr.press/v54/mcmahan17a.html · arXiv:1602.05629

[2] P. Kairouz, H. B. McMahan, et al., "Advances and Open Problems in Federated Learning," *Foundations and Trends in Machine Learning*, 14(1–2):1–210, 2021. https://doi.org/10.1561/2200000083 · arXiv:1912.04977

[3] K. Bonawitz, H. Eichner, W. Grieskamp, et al., "Towards Federated Learning at Scale: System Design," *SysML*, 2019. arXiv:1902.01046

[4] Y. Zhao, M. Li, L. Lai, N. Suda, D. Civin, and V. Chandra, "Federated Learning with Non-IID Data," arXiv:1806.00582, 2018 (rev. 2022). https://doi.org/10.48550/arXiv.1806.00582

[5] T.-M. H. Hsu, H. Qi, and M. Brown, "Measuring the Effects of Non-Identical Data Distribution for Federated Visual Classification," arXiv:1909.06335, 2019.

[6] T. Nishio and R. Yonetani, "Client Selection for Federated Learning with Heterogeneous Resources in Mobile Edge," *IEEE ICC*, 2019. https://doi.org/10.1109/ICC.2019.8761315 · arXiv:1804.08333

[7] L. Yu, R. Albelaihi, X. Sun, N. Ansari, and M. Devetsikiotis, "Jointly Optimizing Client Selection and Resource Management in Wireless Federated Learning for Internet of Things," *IEEE Internet of Things Journal*, 2021. https://doi.org/10.1109/JIOT.2021.3103715

[8] A. Imteaj, U. Thakker, S. Wang, J. Li, and M. H. Amini, "A Survey on Federated Learning for Resource-Constrained IoT Devices," *IEEE Internet of Things Journal*, 2021. https://doi.org/10.1109/JIOT.2021.3095077

[9] L. Fu, H. Zhang, G. Gao, M. Zhang, and X. Liu, "Client Selection in Federated Learning: Principles, Challenges, and Opportunities," arXiv:2211.01549, 2022 (rev. 2023). https://doi.org/10.48550/arXiv.2211.01549

[10] S. Agrawal, S. Sarkar, O. Aouedi, et al., "Federated Learning for intrusion detection system: Concepts, challenges and future directions," *Computer Communications*, 195:346–361, 2022. https://doi.org/10.1016/j.comcom.2022.09.012 · arXiv:2106.09527

[11] T. D. Nguyen, S. Marchal, M. Miettinen, H. Fereidooni, N. Asokan, and A.-R. Sadeghi, "DÏoT: A Federated Self-learning Anomaly Detection System for IoT," *IEEE ICDCS*, 2019. https://doi.org/10.1109/ICDCS.2019.00080 · arXiv:1804.07474

[12] E. C. P. Neto, S. Dadkhah, R. Ferreira, A. Zohourian, R. Lu, and A. A. Ghorbani, "CICIoT2023: A Real-Time Dataset and Benchmark for Large-Scale Attacks in IoT Environment," *Sensors*, 23(13):5941, 2023. https://doi.org/10.3390/s23135941

[13] N. I. Matos Filho, A. Vitorino, M. Ahsan, F. S. H. de Souza, and D. L. Guidoni, "Intrusion Detection in IoT Networks Using Federated Learning," *DCOSS-IoT*, 2025. https://doi.org/10.1109/DCOSS-IOT65416.2025.00109

[14] P. S. Bouzinis, P. I. Radoglou Grammatikis, I. Makris, et al., "StatAvg: Mitigating Data Heterogeneity in Federated Learning for Intrusion Detection Systems," *IEEE Transactions on Network and Service Management*, 2025. https://doi.org/10.1109/TNSM.2025.3564387

[15] M. A. Bilal, I. Ul Islam, S. Idrees, M. Qasim, and M. J. Khan, "Dataset-centric evaluation of federated intrusion detection models in IoT networks," *Scientific Reports*, 2026. https://doi.org/10.1038/s41598-025-32567-w

[16] X. Qiu, T. Parcollet, J. Fernandez-Marques, et al., "A first look into the carbon footprint of federated learning," *Journal of Machine Learning Research*, 24(129):5899–5921, 2023. arXiv:2102.07627

[17] S. Savazzi, V. Rampa, S. Kianoush, and M. Bennis, "An Energy and Carbon Footprint Analysis of Distributed and Federated Learning," *IEEE Transactions on Green Communications and Networking*, 7(1):248–264, 2023. https://doi.org/10.1109/TGCN.2022.3186439 · arXiv:2206.10380

## Review limitations

- Claims are limited to abstracts and publisher summaries; full texts were not systematically coded.
- The review is not exhaustive and excludes non-English work and most pre-2017 FL literature.
- Publication dates for 2025–2026 items reflect the indexed records at review time.
- No quantitative meta-analysis was performed, so cross-paper numbers are not directly comparable.
