const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

const generateDisk = (profile = {}) => {
    const totalBytes = 500 * 1024 ** 3;
    const base = profile.diskPercent ?? 55;
    const usedPercent = Number(
        clamp(base + (Math.random() * 6 - 3), 5, 97).toFixed(2)
    );
    const usedBytes = Math.floor(totalBytes * usedPercent / 100);
    const availableBytes = totalBytes - usedBytes;

    return [{
        filesystem: "SIMULATED",
        mount: "/simulated",
        totalBytes,
        usedBytes,
        availableBytes,
        usedPercent
    }];
};

module.exports = generateDisk;
