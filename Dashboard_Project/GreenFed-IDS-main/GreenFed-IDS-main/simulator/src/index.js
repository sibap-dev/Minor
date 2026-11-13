
try {
    require("dotenv").config();
} catch {
    // dotenv is optional; the dashboard passes environment variables directly.
}

const fs = require("fs");
const path = require("path");

const registerClient = require("./registerClient");
const generateResource = require("./generators/resourceGenerator");
const generateDisk = require("./generators/diskGenerator");
const generateNetwork = require("./generators/networkGenerator");
const sendTelemetry = require("./services/apiService");
const { PROFILES } = require("./profiles");

const API_URL = process.env.API_URL;
const CLIENT_COUNT = Number(process.env.SIMULATOR_CLIENT_COUNT || 5);
const INTERVAL = Number(process.env.COLLECTION_INTERVAL_MS || 10000);
const CLIENT_PREFIX = process.env.SIMULATOR_CLIENT_PREFIX || "client_";
const CREDENTIALS_FILE = process.env.SIMULATOR_CREDENTIALS_FILE
    || path.join(__dirname, "..", ".simulator-credentials.json");

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

function loadCache() {
    try {
        if (!fs.existsSync(CREDENTIALS_FILE)) {
            return [];
        }
        const parsed = JSON.parse(fs.readFileSync(CREDENTIALS_FILE, "utf8"));
        return Array.isArray(parsed) ? parsed : [];
    } catch (error) {
        console.error(`[WARN] Ignoring unreadable credential cache: ${error.message}`);
        return [];
    }
}

function saveCache(clients) {
    fs.mkdirSync(path.dirname(CREDENTIALS_FILE), { recursive: true });
    const temp = `${CREDENTIALS_FILE}.tmp`;
    fs.writeFileSync(temp, JSON.stringify(clients, null, 2));
    fs.renameSync(temp, CREDENTIALS_FILE);
}

async function ensureClient(displayName, cache) {
    const cached = cache.find(item => item.displayName === displayName);
    if (cached?.clientId && cached?.token) {
        console.log(`[REUSE] ${displayName}: ${cached.clientId}`);
        return cached;
    }

    const registered = await registerClient(API_URL, displayName);
    const entry = {
        clientId: registered.clientId,
        displayName,
        token: registered.token
    };
    const index = cache.findIndex(item => item.displayName === displayName);
    if (index >= 0) {
        cache[index] = entry;
    } else {
        cache.push(entry);
    }
    saveCache(cache);
    console.log(`[REGISTERED] ${displayName}: ${entry.clientId}`);
    return entry;
}

async function runSimulator() {
    if (!API_URL) {
        throw new Error("API_URL is missing");
    }

    if (!Number.isInteger(CLIENT_COUNT) || CLIENT_COUNT < 1 || CLIENT_COUNT > 50) {
        throw new Error("Client count must be between 1 and 50");
    }

    if (!Number.isFinite(INTERVAL) || INTERVAL < 1000) {
        throw new Error("Collection interval must be at least 1000 ms");
    }

    console.log("Preparing simulated clients...");
    const cache = loadCache();
    const clients = [];

    for (let i = 1; i <= CLIENT_COUNT; i++) {
        const displayName = `${CLIENT_PREFIX}${i}`;
        const profile = PROFILES[(i - 1) % PROFILES.length];
        const client = await ensureClient(displayName, cache);
        clients.push({ ...client, profile });
    }

    saveCache(cache);
    console.log(`\n${clients.length} simulated clients ready.`);
    console.log("Starting telemetry generation...\n");

    while (true) {
        await Promise.allSettled(
            clients.map(async client => {
                if (Math.random() > client.profile.availability) {
                    return;
                }

                const telemetry = {
                    observedAt: new Date().toISOString(),
                    source: "simulated",
                    collectionVersion: "2.0.0-dashboard",
                    ...generateResource(client.profile),
                    disk: generateDisk(client.profile),
                    network: generateNetwork(client.profile)
                };

                try {
                    await sendTelemetry(API_URL, client.token, telemetry);
                } catch (error) {
                    if (error.status === 401) {
                        try {
                            const registered = await registerClient(
                                API_URL,
                                client.displayName
                            );
                            client.clientId = registered.clientId;
                            client.token = registered.token;
                            const cached = cache.find(
                                item => item.displayName === client.displayName
                            );
                            if (cached) {
                                cached.clientId = registered.clientId;
                                cached.token = registered.token;
                            }
                            saveCache(cache);
                            console.log(
                                `[REFRESHED] ${client.displayName}: ${client.clientId}`
                            );
                        } catch (refreshError) {
                            console.error(
                                `[ERROR] ${client.displayName}: ${refreshError.message}`
                            );
                        }
                        return;
                    }
                    console.error(
                        `[ERROR] ${client.displayName}: ${error.message}`
                    );
                }
            })
        );

        await sleep(INTERVAL);
    }
}

runSimulator().catch(error => {
    console.error("Simulator startup failed:", error.message);
    process.exitCode = 1;
});
