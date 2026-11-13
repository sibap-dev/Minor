
package greenfed_resource_monitor.telemetry;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.OffsetDateTime;
import java.util.HexFormat;

import java.util.List;

import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import greenfed_resource_monitor.client.Client;
import greenfed_resource_monitor.client.ClientCredential;
import greenfed_resource_monitor.client.ClientCredentialRepository;
import greenfed_resource_monitor.client.ClientRepository;
import greenfed_resource_monitor.telemetry.dto.DiskSampleRequest;
import greenfed_resource_monitor.telemetry.dto.NetworkSampleRequest;
import greenfed_resource_monitor.telemetry.dto.TelemetryRequest;
import greenfed_resource_monitor.telemetry.dto.TelemetryResponse;

@Service
public class TelemetryService {

    private final ClientCredentialRepository credentialRepository;
    private final ClientRepository clientRepository;
    private final ResourceSampleRepository sampleRepository;
    private final JdbcTemplate jdbc;

    public TelemetryService(
            ClientCredentialRepository credentialRepository,
            ClientRepository clientRepository,
            ResourceSampleRepository sampleRepository,
            JdbcTemplate jdbc) {
        this.credentialRepository = credentialRepository;
        this.clientRepository = clientRepository;
        this.sampleRepository = sampleRepository;
        this.jdbc = jdbc;
    }

    @Transactional
    public TelemetryResponse record(String token, TelemetryRequest request) {
        if (token == null || token.isBlank()) {
            throw unauthorized();
        }

        String tokenHash = hashToken(token);

        ClientCredential credential = credentialRepository
                .findByTokenHash(tokenHash)
                .orElseThrow(this::unauthorized);

        OffsetDateTime now = OffsetDateTime.now();

        if (credential.getRevokedAt() != null
                || (credential.getExpiresAt() != null
                    && !credential.getExpiresAt().isAfter(now))) {
            throw unauthorized();
        }

        Client client = clientRepository.findById(
                credential.getClient().getClientId())
                .orElseThrow(this::unauthorized);

        if (!client.isEnabled()) {
            throw unauthorized();
        }

        validate(request);

        ResourceSample sample = new ResourceSample(
                client,
                request.observedAt(),
                request.cpuPercent(),
                request.memoryTotalBytes(),
                request.memoryUsedBytes(),
                request.memoryAvailableBytes(),
                request.source());

        sample.setExperimentId(request.experimentId());
        sample.setAgentId(request.agentId());
        sample.setCollectionVersion(request.collectionVersion());

        ResourceSample saved = sampleRepository.save(sample);
        saveExtras(client, request, now);

        client.setLastSeenAt(now);
        credential.setLastUsedAt(now);

        clientRepository.save(client);
        credentialRepository.save(credential);

        return new TelemetryResponse(
                saved.getSampleId(),
                client.getClientId(),
                saved.getExperimentId(),
                saved.getObservedAt(),
                saved.getCpuPercent(),
                saved.getMemoryTotalBytes(),
                saved.getMemoryUsedBytes(),
                saved.getMemoryAvailableBytes(),
                saved.getSource());
    }

    private void validate(TelemetryRequest request) {
        if (request == null
                || request.observedAt() == null
                || request.cpuPercent() == null
                || request.memoryTotalBytes() == null
                || request.memoryUsedBytes() == null
                || request.memoryAvailableBytes() == null
                || request.source() == null) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "Required telemetry fields are missing");
        }

        if (request.cpuPercent() < 0 || request.cpuPercent() > 100) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "CPU must be between 0 and 100");
        }

        if (request.memoryTotalBytes() < 0
                || request.memoryUsedBytes() < 0
                || request.memoryAvailableBytes() < 0
                || request.memoryUsedBytes() > request.memoryTotalBytes()
                || request.memoryAvailableBytes() > request.memoryTotalBytes()) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "Memory values are invalid");
        }

        if (!request.source().equals("simulated")
                && !request.source().equals("measured_client")
                && !request.source().equals("estimated")
                && !request.source().equals("unavailable")) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "Unsupported telemetry source");
        }

        validateDisk(request.disk());
        validateNetwork(request.network());
    }

    private void validateDisk(List<DiskSampleRequest> disks) {
        if (disks == null) {
            return;
        }
        if (disks.size() > 32) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST, "Too many disk samples");
        }
        for (DiskSampleRequest disk : disks) {
            if (disk == null
                    || disk.totalBytes() == null
                    || disk.usedBytes() == null
                    || disk.availableBytes() == null
                    || disk.usedPercent() == null
                    || disk.totalBytes() < 0
                    || disk.usedBytes() < 0
                    || disk.availableBytes() < 0
                    || disk.usedPercent() < 0
                    || disk.usedPercent() > 100
                    || disk.usedBytes() + disk.availableBytes()
                        > disk.totalBytes() + 1) {
                throw new ResponseStatusException(
                        HttpStatus.BAD_REQUEST, "Invalid disk sample");
            }
        }
    }

    private void validateNetwork(List<NetworkSampleRequest> samples) {
        if (samples == null) {
            return;
        }
        if (samples.size() > 32) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST, "Too many network samples");
        }
        for (NetworkSampleRequest sample : samples) {
            if (sample == null
                    || sample.transferBytes() == null
                    || sample.durationMs() == null
                    || sample.bandwidthMbps() == null
                    || sample.transferBytes() < 0
                    || sample.durationMs() <= 0
                    || sample.bandwidthMbps() < 0
                    || (sample.latencyMs() != null && sample.latencyMs() < 0)
                    || (sample.jitterMs() != null && sample.jitterMs() < 0)
                    || (sample.packetLossPercent() != null
                        && (sample.packetLossPercent() < 0
                            || sample.packetLossPercent() > 100))
                    || (sample.availability() != null
                        && (sample.availability() < 0
                            || sample.availability() > 1))) {
                throw new ResponseStatusException(
                        HttpStatus.BAD_REQUEST, "Invalid network sample");
            }
        }
    }

    private void saveExtras(
            Client client,
            TelemetryRequest request,
            OffsetDateTime observedAt) {
        String networkSource = "measured_client".equals(request.source())
                ? "measured_network"
                : request.source();

        if (request.disk() != null) {
            for (DiskSampleRequest disk : request.disk()) {
                jdbc.update("""
                        INSERT INTO disk_samples (
                            client_id, observed_at, filesystem, mount,
                            total_bytes, used_bytes, available_bytes,
                            used_percent, source, collection_version
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        client.getClientId(),
                        observedAt,
                        disk.filesystem(),
                        disk.mount(),
                        disk.totalBytes(),
                        disk.usedBytes(),
                        disk.availableBytes(),
                        disk.usedPercent(),
                        request.source(),
                        request.collectionVersion());
            }
        }

        if (request.network() != null) {
            for (NetworkSampleRequest sample : request.network()) {
                jdbc.update("""
                        INSERT INTO network_samples (
                            client_id, observed_at, latency_ms, transfer_bytes,
                            duration_ms, bandwidth_mbps, jitter_ms,
                            packet_loss_percent, availability, source,
                            method
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        client.getClientId(),
                        observedAt,
                        sample.latencyMs(),
                        sample.transferBytes(),
                        sample.durationMs(),
                        sample.bandwidthMbps(),
                        sample.jitterMs(),
                        sample.packetLossPercent(),
                        sample.availability(),
                        networkSource,
                        "dashboard_ingest:"
                            + (sample.networkInterface() == null
                                ? "unknown"
                                : sample.networkInterface()));
            }
        }
    }

    private String hashToken(String token) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(token.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (java.security.NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 is unavailable", ex);
        }
    }

    private ResponseStatusException unauthorized() {
        return new ResponseStatusException(
                HttpStatus.UNAUTHORIZED,
                "Invalid or inactive agent credential");
    }
}
