const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

const jitter = (value, percent) => {
    const delta = value * percent * (Math.random() * 2 - 1);
    return value + delta;
};

const generateResource = (profile = {}) => {
    const memoryTotalBytes = 8 * 1024 ** 3;
    const cpuPercent = Number(
        clamp(jitter(profile.cpuPercent ?? 50, 0.12), 1, 99).toFixed(2)
    );
    const memoryPercent = Number(
        clamp(jitter(profile.memoryPercent ?? 55, 0.08), 5, 95).toFixed(2)
    );
    const memoryUsedBytes = Math.floor(memoryTotalBytes * memoryPercent / 100);

    return {
        cpuPercent,
        memoryTotalBytes,
        memoryUsedBytes,
        memoryAvailableBytes: memoryTotalBytes - memoryUsedBytes
    };
};

module.exports = generateResource;
