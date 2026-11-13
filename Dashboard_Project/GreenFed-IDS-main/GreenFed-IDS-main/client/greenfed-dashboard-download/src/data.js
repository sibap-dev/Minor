// Static dataset file metadata used by the dataset workspace.
// Class distributions, partitions and experiment metrics are loaded from saved reports/APIs.
export const datasetFiles = [
  { name: "Merged01_clean.csv", records: 712311, type: "Cleaned source dataset" },
  { name: "Merged02_clean.csv", records: 748585, type: "Cleaned source dataset" },
  { name: "train.csv", records: 1170022, type: "Training dataset" },
  { name: "test.csv", records: 290874, type: "Testing dataset" }
];

export const clientProfiles = [
  { id: "client_1", label: "Edge gateway", profile: "Strong resources", cpu: "~25%", memory: "~42%", latency: "~22 ms", bandwidth: "~90 Mbps", packetLoss: "~0.4%", availability: "~0.98" },
  { id: "client_2", label: "Sensor hub", profile: "Moderate resources", cpu: "~55%", memory: "~64%", latency: "~65 ms", bandwidth: "~35 Mbps", packetLoss: "~2.5%", availability: "~0.90" },
  { id: "client_3", label: "Constrained camera", profile: "Constrained", cpu: "~86%", memory: "~81%", latency: "~145 ms", bandwidth: "~12 Mbps", packetLoss: "~7.5%", availability: "~0.70" },
  { id: "client_4", label: "Low-load LAN node", profile: "Balanced", cpu: "~30%", memory: "~48%", latency: "~38 ms", bandwidth: "~70 Mbps", packetLoss: "~1.0%", availability: "~0.95" },
  { id: "client_5", label: "Remote weak-network node", profile: "Network constrained", cpu: "~62%", memory: "~72%", latency: "~310 ms", bandwidth: "~5 Mbps", packetLoss: "~14%", availability: "~0.62" }
];

export const workflowSteps = [
  "Dataset",
  "Client Simulation",
  "Client Context",
  "Client Selection",
  "Local Training",
  "Global Aggregation",
  "Evaluation",
  "Experiment Comparison"
];
