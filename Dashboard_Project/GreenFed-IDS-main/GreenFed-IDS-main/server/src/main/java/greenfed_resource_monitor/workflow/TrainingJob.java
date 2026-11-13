package greenfed_resource_monitor.workflow;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CopyOnWriteArrayList;

public class TrainingJob {

    private final UUID id = UUID.randomUUID();
    private final List<String> log = new CopyOnWriteArrayList<>();
    private final OffsetDateTime createdAt = OffsetDateTime.now();
    private volatile String runId;
    private volatile String name;
    private volatile String status = "queued";
    private volatile String selectionId;
    private volatile String strategy;
    private volatile String scenario;
    private volatile Integer seed;
    private volatile Integer totalRounds;
    private volatile Integer currentRound = 0;
    private volatile OffsetDateTime startedAt;
    private volatile OffsetDateTime finishedAt;
    private volatile String error;
    private volatile Process process;
    private volatile Map<String, Object> request;
    private volatile Object summary;

    public UUID getId() {
        return id;
    }

    public String getRunId() {
        return runId;
    }

    public void setRunId(String runId) {
        this.runId = runId;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public String getSelectionId() {
        return selectionId;
    }

    public void setSelectionId(String selectionId) {
        this.selectionId = selectionId;
    }

    public String getStrategy() {
        return strategy;
    }

    public void setStrategy(String strategy) {
        this.strategy = strategy;
    }

    public String getScenario() {
        return scenario;
    }

    public void setScenario(String scenario) {
        this.scenario = scenario;
    }

    public Integer getSeed() {
        return seed;
    }

    public void setSeed(Integer seed) {
        this.seed = seed;
    }

    public Integer getTotalRounds() {
        return totalRounds;
    }

    public void setTotalRounds(Integer totalRounds) {
        this.totalRounds = totalRounds;
    }

    public Integer getCurrentRound() {
        return currentRound;
    }

    public void setCurrentRound(Integer currentRound) {
        this.currentRound = currentRound;
    }

    public OffsetDateTime getStartedAt() {
        return startedAt;
    }

    public void setStartedAt(OffsetDateTime startedAt) {
        this.startedAt = startedAt;
    }

    public OffsetDateTime getFinishedAt() {
        return finishedAt;
    }

    public void setFinishedAt(OffsetDateTime finishedAt) {
        this.finishedAt = finishedAt;
    }

    public String getError() {
        return error;
    }

    public void setError(String error) {
        this.error = error;
    }

    public Process getProcess() {
        return process;
    }

    public void setProcess(Process process) {
        this.process = process;
    }

    public Map<String, Object> getRequest() {
        return request;
    }

    public void setRequest(Map<String, Object> request) {
        this.request = request;
    }

    public Object getSummary() {
        return summary;
    }

    public void setSummary(Object summary) {
        this.summary = summary;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }

    public List<String> getLog() {
        return log;
    }

    public void addLog(String line) {
        log.add(line);
        if (log.size() > 2000) {
            log.remove(0);
        }
    }

    public Map<String, Object> toMap(boolean includeLog) {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("jobId", id.toString());
        map.put("runId", runId);
        map.put("name", name);
        map.put("status", status);
        map.put("selectionId", selectionId);
        map.put("strategy", strategy);
        map.put("scenario", scenario);
        map.put("seed", seed);
        map.put("currentRound", currentRound);
        map.put("totalRounds", totalRounds);
        map.put("createdAt", createdAt.toString());
        map.put("startedAt", startedAt == null ? null : startedAt.toString());
        map.put("finishedAt", finishedAt == null ? null : finishedAt.toString());
        map.put("error", error);
        map.put("request", request);
        map.put("summary", summary);
        if (includeLog) {
            map.put("log", new ArrayList<>(log));
        } else {
            int from = Math.max(0, log.size() - 40);
            map.put("logTail", new ArrayList<>(log.subList(from, log.size())));
        }
        return map;
    }
}
