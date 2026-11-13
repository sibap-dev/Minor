package greenfed_resource_monitor.workflow;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;

import org.springframework.stereotype.Component;

@Component
public class ProcessRunner {

    public ProcessResult run(
            List<String> command,
            Path workingDirectory,
            Duration timeout,
            Map<String, String> environment) {
        ProcessBuilder builder = new ProcessBuilder(command)
                .directory(workingDirectory.toFile())
                .redirectErrorStream(false);
        if (environment != null) {
            builder.environment().putAll(environment);
        }

        Process process;
        try {
            process = builder.start();
        } catch (IOException ex) {
            return new ProcessResult(-1, "", ex.getMessage(), false);
        }

        CompletableFuture<String> stdout = readAsync(process.getInputStream());
        CompletableFuture<String> stderr = readAsync(process.getErrorStream());

        boolean finished;
        try {
            finished = process.waitFor(timeout.toMillis(), TimeUnit.MILLISECONDS);
            if (!finished) {
                process.destroy();
                if (!process.waitFor(3, TimeUnit.SECONDS)) {
                    process.destroyForcibly();
                }
            }
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            process.destroyForcibly();
            return new ProcessResult(-1, "", "Interrupted", false);
        }

        int exit = finished ? process.exitValue() : -1;
        return new ProcessResult(
                exit,
                stdout.join(),
                stderr.join(),
                !finished);
    }

    private CompletableFuture<String> readAsync(InputStream stream) {
        return CompletableFuture.supplyAsync(() -> {
            try (stream) {
                return new String(stream.readAllBytes(), StandardCharsets.UTF_8);
            } catch (IOException ex) {
                return "";
            }
        });
    }
}
