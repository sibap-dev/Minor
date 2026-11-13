package greenfed_resource_monitor.dashboard;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Read-only aggregates for the monitoring dashboard.
 *
 * All values come from PostgreSQL telemetry tables.  The API does not accept or
 * expose raw CICIoT2023 records.
 */
@Service
public class DashboardService {

    private final JdbcTemplate jdbc;

    public DashboardService(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @Transactional(readOnly = true)
    public Map<String, Object> overview() {
        Map<String, Object> result = new LinkedHashMap<>();

        Long totalClients = jdbc.queryForObject(
                "SELECT COUNT(*) FROM clients", Long.class);
        Long activeClients = jdbc.queryForObject(
                "SELECT COUNT(*) FROM clients WHERE last_seen_at IS NOT NULL "
                + "AND last_seen_at >= NOW() - INTERVAL '5 minutes'",
                Long.class);
        result.put("totalClients", totalClients);
        result.put("activeClients", activeClients);
        result.put("inactiveClients", totalClients - activeClients);
        result.put("runningExperiments", jdbc.queryForObject(
                "SELECT COUNT(*) FROM experiments WHERE status = 'running'",
                Long.class));
        result.put("samplesToday", jdbc.queryForObject(
                "SELECT COUNT(*) FROM resource_samples "
                + "WHERE observed_at >= DATE_TRUNC('day', NOW())",
                Long.class));

        result.put("avgCpu", jdbc.queryForObject(
                "WITH latest AS (SELECT DISTINCT ON (client_id) client_id, cpu_percent "
                + "FROM resource_samples ORDER BY client_id, observed_at DESC) "
                + "SELECT COALESCE(AVG(cpu_percent), 0) FROM latest",
                Double.class));
        result.put("avgMemory", jdbc.queryForObject(
                "WITH latest AS (SELECT DISTINCT ON (client_id) client_id, "
                + "memory_used_bytes, memory_total_bytes FROM resource_samples "
                + "ORDER BY client_id, observed_at DESC) "
                + "SELECT COALESCE(AVG(CASE WHEN memory_total_bytes > 0 "
                + "THEN memory_used_bytes * 100.0 / memory_total_bytes END), 0) FROM latest",
                Double.class));
        result.put("avgDisk", jdbc.queryForObject(
                "WITH latest AS (SELECT DISTINCT ON (client_id) client_id, used_percent "
                + "FROM disk_samples ORDER BY client_id, observed_at DESC) "
                + "SELECT COALESCE(AVG(used_percent), 0) FROM latest",
                Double.class));
        result.put("avgLatency", jdbc.queryForObject(
                "WITH latest AS (SELECT DISTINCT ON (client_id) client_id, latency_ms "
                + "FROM network_samples ORDER BY client_id, observed_at DESC) "
                + "SELECT COALESCE(AVG(latency_ms), 0) FROM latest",
                Double.class));
        result.put("packetLoss", jdbc.queryForObject(
                "WITH latest AS (SELECT DISTINCT ON (client_id) client_id, "
                + "packet_loss_percent FROM network_samples "
                + "ORDER BY client_id, observed_at DESC) "
                + "SELECT COALESCE(AVG(packet_loss_percent), 0) FROM latest",
                Double.class));

        result.put("source", "measured_or_simulated_telemetry");
        return result;
    }

    @Transactional(readOnly = true)
    public List<Map<String, Object>> clients() {
        String sql = """
                WITH latest_resource AS (
                    SELECT DISTINCT ON (client_id) client_id, cpu_percent,
                           memory_used_bytes, memory_total_bytes,
                           memory_available_bytes, source, observed_at
                    FROM resource_samples
                    ORDER BY client_id, observed_at DESC
                ),
                latest_disk AS (
                    SELECT DISTINCT ON (client_id) client_id, used_percent
                    FROM disk_samples
                    ORDER BY client_id, observed_at DESC
                ),
                latest_network AS (
                    SELECT DISTINCT ON (client_id) client_id, latency_ms,
                           bandwidth_mbps, packet_loss_percent, jitter_ms,
                           availability
                    FROM network_samples
                    ORDER BY client_id, observed_at DESC
                )
                SELECT c.client_id,
                       c.display_name,
                       c.agent_mode,
                       c.enabled,
                       c.last_seen_at,
                       r.cpu_percent,
                       CASE WHEN r.memory_total_bytes > 0
                            THEN r.memory_used_bytes * 100.0 / r.memory_total_bytes
                       END AS memory_percent,
                       r.memory_total_bytes,
                       r.memory_available_bytes,
                       d.used_percent AS disk_percent,
                       n.latency_ms,
                       n.bandwidth_mbps,
                       n.packet_loss_percent,
                       n.jitter_ms,
                       n.availability,
                       CASE
                           WHEN n.availability IS NOT NULL THEN n.availability
                           WHEN c.last_seen_at >= NOW() - INTERVAL '5 minutes' THEN 1.0
                           ELSE 0.0
                       END AS availability_effective,
                       CASE
                           WHEN n.availability IS NOT NULL THEN 'simulated_or_measured'
                           ELSE 'derived_from_last_seen'
                       END AS availability_source,
                       COALESCE(r.source, 'unavailable') AS source,
                       r.observed_at AS last_sample_at,
                       EXISTS (
                           SELECT 1 FROM disk_samples ds
                           WHERE ds.client_id = c.client_id
                       ) AS has_disk_samples,
                       EXISTS (
                           SELECT 1 FROM network_samples ns
                           WHERE ns.client_id = c.client_id
                       ) AS has_network_samples
                FROM clients c
                LEFT JOIN latest_resource r ON r.client_id = c.client_id
                LEFT JOIN latest_disk d ON d.client_id = c.client_id
                LEFT JOIN latest_network n ON n.client_id = c.client_id
                ORDER BY c.display_name
                """;
        return jdbc.queryForList(sql);
    }

    @Transactional(readOnly = true)
    public Map<String, Object> timeseries() {
        String resourceSql = """
                SELECT TO_CHAR(bucket, 'HH24:MI') AS time,
                       ROUND(AVG(cpu_percent)::numeric, 2) AS cpu,
                       ROUND(AVG(
                           CASE WHEN memory_total_bytes > 0
                                THEN memory_used_bytes * 100.0 / memory_total_bytes
                           END
                       )::numeric, 2) AS memory
                FROM (
                    SELECT date_trunc('hour', observed_at)
                           + floor(extract(minute FROM observed_at) / 5)
                             * INTERVAL '5 minutes' AS bucket,
                           cpu_percent, memory_used_bytes, memory_total_bytes
                    FROM resource_samples
                    WHERE observed_at >= NOW() - INTERVAL '2 hours'
                ) samples
                GROUP BY bucket
                ORDER BY bucket
                """;
        String networkSql = """
                SELECT TO_CHAR(bucket, 'HH24:MI') AS time,
                       ROUND(AVG(bandwidth_mbps)::numeric, 2) AS bandwidth,
                       ROUND(AVG(latency_ms)::numeric, 2) AS latency,
                       ROUND(AVG(packet_loss_percent)::numeric, 2) AS packet_loss
                FROM (
                    SELECT date_trunc('hour', observed_at)
                           + floor(extract(minute FROM observed_at) / 5)
                             * INTERVAL '5 minutes' AS bucket,
                           bandwidth_mbps, latency_ms, packet_loss_percent
                    FROM network_samples
                    WHERE observed_at >= NOW() - INTERVAL '2 hours'
                ) samples
                GROUP BY bucket
                ORDER BY bucket
                """;
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("resource", jdbc.queryForList(resourceSql));
        result.put("network", jdbc.queryForList(networkSql));
        result.put("bucketMinutes", 5);
        result.put("windowHours", 2);
        return result;
    }
}
