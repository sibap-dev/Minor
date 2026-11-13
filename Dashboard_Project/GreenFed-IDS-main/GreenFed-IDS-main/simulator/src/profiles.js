const PROFILES = [
    {
        key: "edge-gateway-strong",
        label: "Edge gateway, strong resources",
        cpuPercent: 25,
        memoryPercent: 42,
        diskPercent: 55,
        latencyMs: 22,
        bandwidthMbps: 90,
        jitterMs: 3,
        packetLossPercent: 0.4,
        availability: 0.98
    },
    {
        key: "sensor-hub-moderate",
        label: "Sensor hub, moderate resources",
        cpuPercent: 55,
        memoryPercent: 64,
        diskPercent: 68,
        latencyMs: 65,
        bandwidthMbps: 35,
        jitterMs: 9,
        packetLossPercent: 2.5,
        availability: 0.90
    },
    {
        key: "constrained-camera",
        label: "Constrained camera node",
        cpuPercent: 86,
        memoryPercent: 81,
        diskPercent: 88,
        latencyMs: 145,
        bandwidthMbps: 12,
        jitterMs: 22,
        packetLossPercent: 7.5,
        availability: 0.70
    },
    {
        key: "lan-node-low-load",
        label: "Low-load LAN node",
        cpuPercent: 30,
        memoryPercent: 48,
        diskPercent: 45,
        latencyMs: 38,
        bandwidthMbps: 70,
        jitterMs: 5,
        packetLossPercent: 1.0,
        availability: 0.95
    },
    {
        key: "remote-node-weak-network",
        label: "Remote node, weak network",
        cpuPercent: 62,
        memoryPercent: 72,
        diskPercent: 74,
        latencyMs: 310,
        bandwidthMbps: 5,
        jitterMs: 48,
        packetLossPercent: 14.0,
        availability: 0.62
    }
];

module.exports = { PROFILES };
