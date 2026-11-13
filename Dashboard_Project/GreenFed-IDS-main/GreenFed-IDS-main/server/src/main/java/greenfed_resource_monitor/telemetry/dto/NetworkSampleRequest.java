package greenfed_resource_monitor.telemetry.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record NetworkSampleRequest(
        @JsonProperty("interface") String networkInterface,
        Long transferBytes,
        Double durationMs,
        Double bandwidthMbps,
        Double latencyMs,
        Double jitterMs,
        Double packetLossPercent,
        Double availability) {
}
