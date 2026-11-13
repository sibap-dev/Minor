package greenfed_resource_monitor.workflow;

import java.nio.file.Files;
import java.nio.file.Path;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * Filesystem and process settings for the local research workflow.
 *
 * Paths are auto-detected by walking up from the process working directory so
 * the server can be started from the repository root, the server directory, or
 * an IDE without hard-coded absolute paths.
 */
@Component
@ConfigurationProperties(prefix = "greenfed")
public class WorkflowProperties {

    private String federatedDir;
    private String python = "python";
    private String simulatorDir;
    private String simulatorNode = "node";
    private String simulatorApiUrl = "http://127.0.0.1:4000";
    private int simulatorClientCount = 5;
    private int simulatorIntervalMs = 10000;

    public String getFederatedDir() {
        return federatedDir;
    }

    public void setFederatedDir(String federatedDir) {
        this.federatedDir = federatedDir;
    }

    public String getPython() {
        return python;
    }

    public void setPython(String python) {
        this.python = python;
    }

    public String getSimulatorDir() {
        return simulatorDir;
    }

    public void setSimulatorDir(String simulatorDir) {
        this.simulatorDir = simulatorDir;
    }

    public String getSimulatorNode() {
        return simulatorNode;
    }

    public void setSimulatorNode(String simulatorNode) {
        this.simulatorNode = simulatorNode;
    }

    public String getSimulatorApiUrl() {
        return simulatorApiUrl;
    }

    public void setSimulatorApiUrl(String simulatorApiUrl) {
        this.simulatorApiUrl = simulatorApiUrl;
    }

    public int getSimulatorClientCount() {
        return simulatorClientCount;
    }

    public void setSimulatorClientCount(int simulatorClientCount) {
        this.simulatorClientCount = simulatorClientCount;
    }

    public int getSimulatorIntervalMs() {
        return simulatorIntervalMs;
    }

    public void setSimulatorIntervalMs(int simulatorIntervalMs) {
        this.simulatorIntervalMs = simulatorIntervalMs;
    }

    public Path federatedPath() {
        if (federatedDir != null && !federatedDir.isBlank()) {
            Path path = Path.of(federatedDir).toAbsolutePath().normalize();
            if (Files.isDirectory(path)) {
                return path;
            }
        }
        return findUpwards("federated/run_experiment.py", "federated");
    }

    public Path resultsPath() {
        return federatedPath().resolve("results");
    }

    public Path selectionsPath() {
        return resultsPath().resolve("selections");
    }

    public Path simulatorPath() {
        if (simulatorDir != null && !simulatorDir.isBlank()) {
            Path path = Path.of(simulatorDir).toAbsolutePath().normalize();
            if (Files.isDirectory(path)) {
                return path;
            }
        }
        Path current = Path.of(System.getProperty("user.dir")).toAbsolutePath().normalize();
        for (Path candidate = current; candidate != null; candidate = candidate.getParent()) {
            Path direct = candidate.resolve("simulator");
            if (Files.isRegularFile(direct.resolve("src/index.js"))) {
                return direct;
            }
            Path nested = candidate.resolve(
                    "GreenFed-IDS-main/GreenFed-IDS-main/simulator");
            if (Files.isRegularFile(nested.resolve("src/index.js"))) {
                return nested;
            }
        }
        throw new IllegalStateException("Simulator directory not found");
    }

    private Path findUpwards(String marker, String directoryName) {
        Path current = Path.of(System.getProperty("user.dir")).toAbsolutePath().normalize();
        for (Path candidate = current; candidate != null; candidate = candidate.getParent()) {
            if (Files.isRegularFile(candidate.resolve(marker))) {
                return candidate.resolve(directoryName);
            }
            Path nested = candidate.resolve(
                    "GreenFed-IDS-main/GreenFed-IDS-main/" + marker);
            if (Files.isRegularFile(nested)) {
                return nested.getParent().getParent();
            }
        }
        throw new IllegalStateException(
                "Federated learning directory not found. Set greenfed.federated-dir.");
    }
}
