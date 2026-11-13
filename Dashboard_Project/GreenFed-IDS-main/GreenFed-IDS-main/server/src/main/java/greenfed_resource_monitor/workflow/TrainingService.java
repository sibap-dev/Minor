package greenfed_resource_monitor.workflow;

import java.io.BufferedReader;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.OffsetDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

@Service
public class TrainingService {

    private static final Pattern ROUND_PATTERN = Pattern.compile("\\[round (\\d+)\\]");

    private final WorkflowProperties properties;
    private final SelectionService selectionService;
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final Map<UUID, TrainingJob> jobs = new ConcurrentHashMap<>();

    public TrainingService(
            WorkflowProperties properties,
            SelectionService selectionService) {
        this.properties = properties;
        this.selectionService = selectionService;
    }

    public Map<String, Object> start(TrainingRequest request) {
        if (request.selectionId() == null || request.selectionId().isBlank()) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "Execute a client selection before training");
        }

        Map<String, Object> selection = selectionService.get(request.selectionId());
        String strategy = String.valueOf(selection.get("strategy"));
        String scenario = String.valueOf(selection.get("scenario"));
        int selectionSeed = asInt(selection.get("seed"), 42);
        int seed = request.seed() == null ? selectionSeed : request.seed();

        if (request.scenario() != null
                && !request.scenario().isBlank()
                && !request.scenario().equals(scenario)) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "Training scenario does not match the selection scenario");
        }
        if (seed != selectionSeed) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "Training seed does not match the selection seed");
        }

        int rounds = clamp(request.rounds(), 2, 1, 20, "rounds");
        int localEpochs = clamp(request.localEpochs(), 1, 1, 10, "localEpochs");
        int batchSize = clamp(request.batchSize(), 256, 1, 4096, "batchSize");
        double learningRate = request.learningRate() == null
                ? 0.001
                : request.learningRate();
        if (learningRate <= 0 || learningRate > 1) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "learningRate must be in (0, 1]");
        }
        double validationFraction = request.validationFraction() == null
                ? 0.1
                : request.validationFraction();
        if (validationFraction < 0 || validationFraction >= 0.9) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "validationFraction must be in [0, 0.9)");
        }
        int numThreads = clamp(request.numThreads(), 4, 1, 32, "numThreads");
        String classWeightMode = request.classWeightMode() == null
                || request.classWeightMode().isBlank()
                ? "none"
                : request.classWeightMode();
        if (!classWeightMode.equals("none") && !classWeightMode.equals("balanced")) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "classWeightMode must be none or balanced");
        }

        String runId = "dashboard_"
                + OffsetDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss"))
                + "_" + scenario + "_s" + seed + "_"
                + UUID.randomUUID().toString().substring(0, 8);
        Path runDir = properties.resultsPath().resolve(runId);

        TrainingJob job = new TrainingJob();
        job.setRunId(runId);
        job.setName(request.name() == null || request.name().isBlank()
                ? "Dashboard experiment " + runId
                : request.name().trim());
        job.setSelectionId(request.selectionId());
        job.setStrategy(strategy);
        job.setScenario(scenario);
        job.setSeed(seed);
        job.setTotalRounds(rounds);
        job.setStatus("starting");
        job.setRequest(requestMap(request, selection));

        List<String> command = new ArrayList<>();
        command.add(properties.getPython());
        command.add("run_experiment.py");
        command.add("--scenario");
        command.add(scenario);
        command.add("--strategy");
        command.add(strategy);
        command.add("--rounds");
        command.add(Integer.toString(rounds));
        command.add("--local-epochs");
        command.add(Integer.toString(localEpochs));
        command.add("--batch-size");
        command.add(Integer.toString(batchSize));
        command.add("--lr");
        command.add(Double.toString(learningRate));
        command.add("--seed");
        command.add(Integer.toString(seed));
        command.add("--num-select");
        command.add(Integer.toString(asInt(selection.get("numSelect"), 3)));
        command.add("--validation-fraction");
        command.add(Double.toString(validationFraction));
        command.add("--class-weight-mode");
        command.add(classWeightMode);
        command.add("--num-threads");
        command.add(Integer.toString(numThreads));
        command.add("--selection-file");
        command.add(properties.selectionsPath()
                .resolve(request.selectionId() + ".json")
                .toAbsolutePath().toString());
        command.add("--run-id");
        command.add(runId);
        command.add("--tag");
        command.add("dashboard");
        if (request.maxSamplesPerClient() != null) {
            if (request.maxSamplesPerClient() < 1) {
                throw new ResponseStatusException(
                        HttpStatus.BAD_REQUEST,
                        "maxSamplesPerClient must be positive");
            }
            command.add("--max-samples-per-client");
            command.add(Integer.toString(request.maxSamplesPerClient()));
        }

        try {
            Files.createDirectories(runDir);
            ProcessBuilder builder = new ProcessBuilder(command)
                    .directory(properties.federatedPath().toFile())
                    .redirectErrorStream(true);
            builder.environment().put("PYTHONUNBUFFERED", "1");
            Process process = builder.start();
            job.setProcess(process);
            job.setStatus("running");
            job.setStartedAt(OffsetDateTime.now());
            jobs.put(job.getId(), job);

            Thread reader = new Thread(
                    () -> follow(job, process, runDir),
                    "training-" + runId);
            reader.setDaemon(true);
            reader.start();
        } catch (IOException ex) {
            job.setStatus("failed");
            job.setError("Unable to start training: " + ex.getMessage());
            job.setFinishedAt(OffsetDateTime.now());
            jobs.put(job.getId(), job);
            writeJobFile(job, runDir);
        }

        return job.toMap(true);
    }

    public List<Map<String, Object>> list() {
        return jobs.values().stream()
                .sorted((a, b) -> b.getCreatedAt().compareTo(a.getCreatedAt()))
                .map(job -> job.toMap(false))
                .toList();
    }

    public Map<String, Object> get(UUID jobId) {
        TrainingJob job = jobs.get(jobId);
        if (job == null) {
            throw new ResponseStatusException(
                    HttpStatus.NOT_FOUND, "Training job not found");
        }
        return job.toMap(true);
    }

    public Map<String, Object> cancel(UUID jobId) {
        TrainingJob job = jobs.get(jobId);
        if (job == null) {
            throw new ResponseStatusException(
                    HttpStatus.NOT_FOUND, "Training job not found");
        }
        Process process = job.getProcess();
        if (process != null && process.isAlive()) {
            process.destroy();
            try {
                if (!process.waitFor(5, java.util.concurrent.TimeUnit.SECONDS)) {
                    process.destroyForcibly();
                }
            } catch (InterruptedException ex) {
                Thread.currentThread().interrupt();
                process.destroyForcibly();
            }
            job.setStatus("cancelled");
            job.setFinishedAt(OffsetDateTime.now());
            writeJobFile(job, properties.resultsPath().resolve(job.getRunId()));
        }
        return job.toMap(true);
    }

    private void follow(TrainingJob job, Process process, Path runDir) {
        try (BufferedReader reader = process.inputReader(StandardCharsets.UTF_8)) {
            String line;
            while ((line = reader.readLine()) != null) {
                job.addLog(line);
                Matcher matcher = ROUND_PATTERN.matcher(line);
                if (matcher.find()) {
                    job.setCurrentRound(Integer.parseInt(matcher.group(1)));
                }
            }
        } catch (IOException ex) {
            job.addLog("log reader failed: " + ex.getMessage());
        }

        int exit;
        try {
            exit = process.waitFor();
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            exit = -1;
        }

        job.setFinishedAt(OffsetDateTime.now());
        if (exit == 0) {
            job.setStatus("completed");
            job.setCurrentRound(job.getTotalRounds());
            Path summary = runDir.resolve("summary.json");
            if (Files.isRegularFile(summary)) {
                try {
                    job.setSummary(objectMapper.readValue(
                            Files.readString(summary, StandardCharsets.UTF_8),
                            new TypeReference<List<Map<String, Object>>>() {}));
                } catch (IOException ex) {
                    job.addLog("summary parse failed: " + ex.getMessage());
                }
            }
        } else if (!"cancelled".equals(job.getStatus())) {
            job.setStatus("failed");
            job.setError("Training process exited with code " + exit);
        }
        writeJobFile(job, runDir);
    }

    private void writeJobFile(TrainingJob job, Path runDir) {
        if (runDir == null || job.getRunId() == null) {
            return;
        }
        try {
            Files.createDirectories(runDir);
            Map<String, Object> payload = new LinkedHashMap<>(job.toMap(true));
            payload.put("managedBy", "dashboard");
            payload.put("selectionInput", job.getSelectionId());
            Files.writeString(
                    runDir.resolve("dashboard_job.json"),
                    objectMapper.writerWithDefaultPrettyPrinter()
                            .writeValueAsString(payload),
                    StandardCharsets.UTF_8);
            Files.write(
                    runDir.resolve("dashboard_job.log"),
                    String.join(System.lineSeparator(), job.getLog())
                            .getBytes(StandardCharsets.UTF_8));
        } catch (IOException ignored) {
            // The training result remains the source of truth; job metadata is auxiliary.
        }
    }

    private Map<String, Object> requestMap(
            TrainingRequest request,
            Map<String, Object> selection) {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("name", request.name());
        map.put("selectionId", request.selectionId());
        map.put("strategy", selection.get("strategy"));
        map.put("scenario", selection.get("scenario"));
        map.put("seed", selection.get("seed"));
        map.put("selectedClients", selection.get("selected"));
        map.put("constraintsRelaxed", selection.get("constraints_relaxed"));
        map.put("rounds", request.rounds());
        map.put("localEpochs", request.localEpochs());
        map.put("batchSize", request.batchSize());
        map.put("learningRate", request.learningRate());
        map.put("validationFraction", request.validationFraction());
        map.put("maxSamplesPerClient", request.maxSamplesPerClient());
        map.put("classWeightMode", request.classWeightMode());
        map.put("numThreads", request.numThreads());
        return map;
    }

    private int clamp(
            Integer value,
            int fallback,
            int minimum,
            int maximum,
            String name) {
        int resolved = value == null ? fallback : value;
        if (resolved < minimum || resolved > maximum) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    name + " must be between " + minimum + " and " + maximum);
        }
        return resolved;
    }

    private int asInt(Object value, int fallback) {
        if (value instanceof Number number) {
            return number.intValue();
        }
        try {
            return Integer.parseInt(String.valueOf(value));
        } catch (RuntimeException ex) {
            return fallback;
        }
    }
}
