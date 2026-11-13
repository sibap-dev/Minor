package greenfed_resource_monitor.workflow;

import java.util.Map;

public record SelectionRequest(
        String scenario,
        String strategy,
        Integer seed,
        Integer round,
        Integer numSelect,
        Double minAvailability,
        Double maxCpuPercent,
        Double minMemoryAvailableMb,
        Double maxDiskPercent,
        Double maxLatencyMs,
        Double maxPacketLossPercent,
        Map<String, Double> weights) {
}
