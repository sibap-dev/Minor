package greenfed_resource_monitor.workflow;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

@Service
public class ExperimentHistoryService {

    private final WorkflowProperties properties;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public ExperimentHistoryService(WorkflowProperties properties) {
        this.properties = properties;
    }

    public List<Map<String, Object>> list() {
        Path root = properties.resultsPath();
        if (!Files.isDirectory(root)) {
            return List.of();
        }
        try (Stream<Path> stream = Files.list(root)) {
            List<Map<String, Object>> runs = new ArrayList<>();
            stream.filter(Files::isDirectory)
                    .filter(path -> Files.isRegularFile(path.resolve("summary.json")))
                    .forEach(path -> {
                        try {
                            runs.add(describe(path));
                        } catch (RuntimeException ignored) {
                            // A malformed historical directory must not hide valid runs.
                        }
                    });
            runs.sort(Comparator.comparing(
                    run -> String.valueOf(run.get("createdAt")),
                    Comparator.reverseOrder()));
            return runs;
        } catch (IOException ex) {
            throw new ResponseStatusException(
                    HttpStatus.INTERNAL_SERVER_ERROR,
                    "Unable to scan experiment results");
        }
    }

    public Map<String, Object> get(String runId) {
        Path dir = runDirectory(runId);
        if (!Files.isRegularFile(dir.resolve("summary.json"))) {
            throw new ResponseStatusException(
                    HttpStatus.NOT_FOUND, "Experiment run not found");
        }
        Map<String, Object> run = describe(dir);
        run.put("metadata", readJson(dir.resolve("run_metadata.json"), Map.class));
        if (Files.isRegularFile(dir.resolve("dashboard_job.json"))) {
            run.put("dashboardJob", readJson(dir.resolve("dashboard_job.json"), Map.class));
        }
        return run;
    }

    public Map<String, Object> strategyResults(String runId, String strategy) {
        if (!List.of("all", "random", "resource", "context").contains(strategy)) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST, "Unknown strategy");
        }
        Path dir = runDirectory(runId);
        Path path = dir.resolve(strategy).resolve("results.json");
        if (!Files.isRegularFile(path)) {
            throw new ResponseStatusException(
                    HttpStatus.NOT_FOUND, "Strategy result not found");
        }
        return readJson(path, Map.class);
    }

    private Map<String, Object> describe(Path dir) {
        Map<String, Object> run = new LinkedHashMap<>();
        Map<String, Object> metadata = readJson(
                dir.resolve("run_metadata.json"), Map.class);
        Object summary = readJson(dir.resolve("summary.json"), List.class);
        boolean dashboardManaged = Files.isRegularFile(
                dir.resolve("dashboard_job.json"));

        run.put("runId", dir.getFileName().toString());
        run.put("createdAt", metadata.getOrDefault(
                "created_at",
                safeModified(dir)));
        run.put("scenario", metadata.get("scenario"));
        run.put("strategies", metadata.getOrDefault("strategies", List.of()));
        run.put("trainConfig", metadata.getOrDefault("train_config", Map.of()));
        run.put("selectionConfig", metadata.getOrDefault("selection_config", Map.of()));
        run.put("context", metadata.getOrDefault("context", Map.of()));
        run.put("summary", summary);
        run.put("source", dashboardManaged
                ? "dashboard_execution"
                : "historical_artifact");
        run.put("executionLabel", dashboardManaged
                ? "New dashboard execution"
                : "Historical verified artifact");
        run.put("dashboardManaged", dashboardManaged);
        return run;
    }

    private Path runDirectory(String runId) {
        if (runId == null
                || runId.isBlank()
                || !Path.of(runId).getFileName().toString().equals(runId)) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST, "Invalid run id");
        }
        return properties.resultsPath().resolve(runId);
    }

    @SuppressWarnings("unchecked")
    private <T> T readJson(Path path, Class<T> type) {
        if (!Files.isRegularFile(path)) {
            if (type == Map.class) {
                return (T) Map.of();
            }
            if (type == List.class) {
                return (T) List.of();
            }
            return null;
        }
        try {
            String json = Files.readString(path, StandardCharsets.UTF_8);
            if (type == Map.class) {
                return (T) objectMapper.readValue(
                        json,
                        new TypeReference<Map<String, Object>>() {});
            }
            return (T) objectMapper.readValue(
                    json,
                    new TypeReference<List<Map<String, Object>>>() {});
        } catch (IOException ex) {
            throw new ResponseStatusException(
                    HttpStatus.INTERNAL_SERVER_ERROR,
                    "Unable to read experiment artifact");
        }
    }

    private String safeModified(Path dir) {
        try {
            return Files.getLastModifiedTime(dir).toInstant().toString();
        } catch (IOException ex) {
            return "";
        }
    }
}
