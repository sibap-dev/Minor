package greenfed_resource_monitor.telemetry.dto;

public record DiskSampleRequest(
        String filesystem,
        String mount,
        Long totalBytes,
        Long usedBytes,
        Long availableBytes,
        Double usedPercent) {
}
