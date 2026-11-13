package greenfed_resource_monitor.workflow;

import java.io.BufferedReader;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.OffsetDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.TimeUnit;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import jakarta.annotation.PreDestroy;

@Service
public class SimulationService {

    private final WorkflowProperties properties;
    private final List<String> log = new CopyOnWriteArrayList<>();
    private volatile Process process;
    private volatile OffsetDateTime startedAt;
    private volatile String error;

    public SimulationService(WorkflowProperties properties) {
        this.properties = properties;
    }

    public synchronized Map<String, Object> start() {
        if (process != null && process.isAlive()) {
            return status();
        }
        Path simulator = properties.simulatorPath();
        Path credentials = simulator.resolve(".simulator-credentials.json");
        try {
            Files.createDirectories(simulator);
            ProcessBuilder builder = new ProcessBuilder(
                    properties.getSimulatorNode(), "src/index.js")
                    .directory(simulator.toFile())
                    .redirectErrorStream(true);
            Map<String, String> env = builder.environment();
            env.put("API_URL", properties.getSimulatorApiUrl());
            env.put("SIMULATOR_CLIENT_COUNT",
                    Integer.toString(properties.getSimulatorClientCount()));
            env.put("COLLECTION_INTERVAL_MS",
                    Integer.toString(properties.getSimulatorIntervalMs()));
            env.put("SIMULATOR_CREDENTIALS_FILE", credentials.toString());
            env.put("SIMULATOR_CLIENT_PREFIX", "client_");
            env.put("SIMULATOR_PROFILE_MODE", "greenfed");

            process = builder.start();
            startedAt = OffsetDateTime.now();
            error = null;
            log.clear();
            log.add("Simulator started with pid " + process.pid());

            Thread reader = new Thread(
                    () -> follow(process),
                    "greenfed-simulator");
            reader.setDaemon(true);
            reader.start();
        } catch (IOException ex) {
            error = ex.getMessage();
            throw new ResponseStatusException(
                    HttpStatus.INTERNAL_SERVER_ERROR,
                    "Unable to start simulator: " + ex.getMessage());
        }
        return status();
    }

    public synchronized Map<String, Object> stop() {
        Process current = process;
        if (current != null && current.isAlive()) {
            current.destroy();
            try {
                if (!current.waitFor(5, TimeUnit.SECONDS)) {
                    current.destroyForcibly();
                }
            } catch (InterruptedException ex) {
                Thread.currentThread().interrupt();
                current.destroyForcibly();
            }
            log.add("Simulator stopped");
        }
        return status();
    }

    public Map<String, Object> status() {
        Process current = process;
        boolean running = current != null && current.isAlive();
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("running", running);
        map.put("pid", running ? current.pid() : null);
        map.put("startedAt", startedAt == null ? null : startedAt.toString());
        map.put("clientCount", properties.getSimulatorClientCount());
        map.put("intervalMs", properties.getSimulatorIntervalMs());
        map.put("apiUrl", properties.getSimulatorApiUrl());
        map.put("error", error);
        map.put("logTail", tail(log, 60));
        return map;
    }

    private void follow(Process process) {
        try (BufferedReader reader = process.inputReader(StandardCharsets.UTF_8)) {
            String line;
            while ((line = reader.readLine()) != null) {
                log.add(line);
                if (log.size() > 500) {
                    log.remove(0);
                }
            }
        } catch (IOException ex) {
            log.add("Simulator log reader failed: " + ex.getMessage());
        }
        if (process.isAlive()) {
            return;
        }
        try {
            int exit = process.waitFor();
            log.add("Simulator process exited with code " + exit);
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
        }
    }

    private List<String> tail(List<String> values, int limit) {
        int from = Math.max(0, values.size() - limit);
        return List.copyOf(values.subList(from, values.size()));
    }

    @PreDestroy
    public void shutdown() {
        stop();
    }
}
