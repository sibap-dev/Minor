package greenfed_resource_monitor.workflow;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

@Service
public class SelectionService {

    private final WorkflowProperties properties;
    private final ProcessRunner processRunner;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public SelectionService(
            WorkflowProperties properties,
            ProcessRunner processRunner) {
        this.properties = properties;
        this.processRunner = processRunner;
    }

    public Map<String, Object> execute(SelectionRequest request) {
        String scenario = normalizeScenario(request.scenario());
        String strategy = normalizeStrategy(request.strategy());
        int seed = request.seed() == null ? 42 : request.seed();
        int round = request.round() == null ? 0 : request.round();
        int numSelect = request.numSelect() == null ? 3 : request.numSelect();

        if (numSelect < 1 || numSelect > 10) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "numSelect must be between 1 and 10");
        }

        List<String> command = new ArrayList<>();
        command.add(properties.getPython());
        command.add("select_clients.py");
        command.add("--scenario");
        command.add(scenario);
        command.add("--strategy");
        command.add(strategy);
        command.add("--num-select");
        command.add(Integer.toString(numSelect));
        command.add("--seed");
        command.add(Integer.toString(seed));
        command.add("--round");
        command.add(Integer.toString(round));
        addDouble(command, "--min-availability", request.minAvailability(), 0.50);
        addDouble(command, "--max-cpu-percent", request.maxCpuPercent(), 95.0);
        addDouble(command, "--min-memory-available-mb",
                request.minMemoryAvailableMb(), 128.0);
        addDouble(command, "--max-disk-percent", request.maxDiskPercent(), 98.0);
        addDouble(command, "--max-latency-ms", request.maxLatencyMs(), 1000.0);
        addDouble(command, "--max-packet-loss-percent",
                request.maxPacketLossPercent(), 50.0);

        Path weightsFile = null;
        if (request.weights() != null && !request.weights().isEmpty()) {
            try {
                weightsFile = java.nio.file.Files.createTempFile(
                        properties.selectionsPath(), "weights-", ".json");
                java.nio.file.Files.writeString(
                        weightsFile,
                        objectMapper.writeValueAsString(request.weights()),
                        java.nio.charset.StandardCharsets.UTF_8);
                command.add("--weights-file");
                command.add(weightsFile.toAbsolutePath().toString());
            } catch (IOException ex) {
                throw new ResponseStatusException(
                        HttpStatus.BAD_REQUEST, "Invalid weights");
            }
        }

        ProcessResult result = processRunner.run(
                command,
                properties.federatedPath(),
                Duration.ofSeconds(90),
                Map.of("PYTHONUNBUFFERED", "1"));

        try {
            if (weightsFile != null) {
                java.nio.file.Files.deleteIfExists(weightsFile);
            }
        } catch (IOException ignored) {
        }

        if (result.timedOut()) {
            throw new ResponseStatusException(
                    HttpStatus.GATEWAY_TIMEOUT,
                    "Selection timed out");
        }
        if (result.exitCode() != 0) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "Selection failed: " + tail(result.stderr()));
        }

        Map<String, Object> payload;
        try {
            payload = objectMapper.readValue(
                    result.stdout(),
                    new TypeReference<Map<String, Object>>() {});
        } catch (IOException ex) {
            throw new ResponseStatusException(
                    HttpStatus.INTERNAL_SERVER_ERROR,
                    "Selection CLI returned invalid JSON");
        }

        String selectionId = UUID.randomUUID().toString();
        payload.put("selectionId", selectionId);
        payload.put("createdAt", OffsetDateTime.now().toString());
        payload.put("execution", "live_python_selection");
        payload.put("scenario", scenario);
        payload.put("seed", seed);
        payload.put("round", round);
        payload.put("numSelect", numSelect);

        Path selections = properties.selectionsPath();
        try {
            Files.createDirectories(selections);
            String json = objectMapper.writerWithDefaultPrettyPrinter()
                    .writeValueAsString(payload);
            Files.writeString(
                    selections.resolve(selectionId + ".json"),
                    json,
                    StandardCharsets.UTF_8);
            Files.writeString(
                    selections.resolve("latest.json"),
                    json,
                    StandardCharsets.UTF_8);
        } catch (IOException ex) {
            throw new ResponseStatusException(
                    HttpStatus.INTERNAL_SERVER_ERROR,
                    "Unable to save selection result");
        }

        return payload;
    }

    public Map<String, Object> get(String selectionId) {
        validateId(selectionId);
        Path path = properties.selectionsPath().resolve(selectionId + ".json");
        if (!Files.isRegularFile(path)) {
            throw new ResponseStatusException(
                    HttpStatus.NOT_FOUND, "Selection not found");
        }
        return read(path);
    }

    public Map<String, Object> latest() {
        Path path = properties.selectionsPath().resolve("latest.json");
        if (!Files.isRegularFile(path)) {
            throw new ResponseStatusException(
                    HttpStatus.NOT_FOUND,
                    "No selection has been executed yet");
        }
        return read(path);
    }

    private Map<String, Object> read(Path path) {
        try {
            return objectMapper.readValue(
                    Files.readString(path, StandardCharsets.UTF_8),
                    new TypeReference<Map<String, Object>>() {});
        } catch (IOException ex) {
            throw new ResponseStatusException(
                    HttpStatus.INTERNAL_SERVER_ERROR,
                    "Unable to read selection result");
        }
    }

    private void validateId(String selectionId) {
        try {
            UUID.fromString(selectionId);
        } catch (RuntimeException ex) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST, "Invalid selection id");
        }
    }

    private String normalizeScenario(String value) {
        String scenario = value == null || value.isBlank() ? "iid" : value;
        if (!scenario.equals("iid") && !scenario.equals("non_iid")) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "scenario must be iid or non_iid");
        }
        return scenario;
    }

    private String normalizeStrategy(String value) {
        String strategy = value == null || value.isBlank() ? "context" : value;
        if (!List.of("all", "random", "resource", "context").contains(strategy)) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "strategy must be all, random, resource or context");
        }
        return strategy;
    }

    private void addDouble(
            List<String> command,
            String name,
            Double value,
            double fallback) {
        command.add(name);
        command.add(Double.toString(value == null ? fallback : value));
    }

    private String tail(String text) {
        if (text == null) {
            return "";
        }
        String trimmed = text.trim();
        return trimmed.length() <= 1200
                ? trimmed
                : trimmed.substring(trimmed.length() - 1200);
    }
}
