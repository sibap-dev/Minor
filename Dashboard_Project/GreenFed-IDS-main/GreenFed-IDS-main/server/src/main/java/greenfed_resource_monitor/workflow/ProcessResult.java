package greenfed_resource_monitor.workflow;

public record ProcessResult(
        int exitCode,
        String stdout,
        String stderr,
        boolean timedOut) {
}
