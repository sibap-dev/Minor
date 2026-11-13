const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

const jitter = (value, percent) => {
    const delta = value * percent * (Math.random() * 2 - 1);
    return value + delta;
};

const generateNetwork = (profile = {}) => {
    const durationMs = 10000;
    const bandwidthMbps = Number(
        clamp(jitter(profile.bandwidthMbps ?? 40, 0.15), 0.5, 500).toFixed(2)
    );
    const latencyMs = Number(
        clamp(jitter(profile.latencyMs ?? 60, 0.15), 1, 5000).toFixed(2)
    );
    const packetLossPercent = Number(
        clamp(jitter(profile.packetLossPercent ?? 2, 0.30), 0, 100).toFixed(2)
    );
    const jitterMs = Number(
        clamp(jitter(profile.jitterMs ?? 8, 0.25), 0, 1000).toFixed(2)
    );
    const availability = Number(
        clamp(jitter(profile.availability ?? 0.9, 0.03), 0, 1).toFixed(4)
    );
    const transferBytes = Math.floor(
        bandwidthMbps * 1000000 * durationMs / 8000
    );

    return [{
        interface: "SIMULATED-NETWORK",
        transferBytes,
        durationMs,
        bandwidthMbps,
        latencyMs,
        jitterMs,
        packetLossPercent,
        availability
    }];
};

module.exports = generateNetwork;
