# API Documentation

This document covers the HTTP APIs used by the dashboard and agents. Two services expose endpoints:

- **Spring Boot** (`server/`, port 4000) is the primary backend for client registration, dashboard aggregates, dataset summary, and CPU/memory telemetry.
- **Express** (`api/`, port 5000) is the legacy telemetry ingest used by the Node agent for CPU, memory, disk, and network payloads.

Both use the same PostgreSQL database and the same `clients` / `client_credentials` schema. Running both against one database is supported but can create duplicate client records if registration is repeated.

Base URLs:

- Spring: `http://localhost:4000`
- Express: `http://localhost:5000`

All request and response bodies are JSON. Timestamps are ISO-8601 offset date-times.

## 1. Authentication

Client registration returns a raw token **once**. Only its SHA-256 hash is stored. Send it as:

```
Authorization: Bearer <token>
```

Telemetry and heartbeat endpoints require it. Registration, dashboard reads, and dataset reads do not. This is a bearer credential, not a full authorization system: anyone with the token can post telemetry for that client.

Tokens are checked for revocation (`revoked_at`) and expiry (`expires_at`). Disabled clients are rejected.

## 2. Spring Boot endpoints

### 2.1 POST `/api/clients`

Register a client and obtain a token.

Request:

```json
{
  "displayName": "gateway-01",
  "agentMode": "real_agent"
}
```

Validation:

- `displayName`: required, trimmed, maximum 120 characters.
- `agentMode`: required, one of `real_agent`, `simulated_agent`.

Response `201 Created`:

```json
{
  "clientId": "0f1c2d3e-4a5b-6c7d-8e9f-001122334455",
  "displayName": "gateway-01",
  "agentMode": "real_agent",
  "enabled": true,
  "createdAt": "2026-11-12T15:00:00+00:00",
  "updatedAt": "2026-11-12T15:00:00+00:00",
  "agentToken": "64-hex-character-token"
}
```

`agentToken` is not retrievable later. Store it immediately.

Errors:

- `400 Bad Request`: blank/long display name, invalid agent mode, malformed JSON.
- `500 Internal Server Error`: persistence failure.

### 2.2 GET `/api/clients`

Returns all clients as JSON entities. Fields include `clientId`, `displayName`, `agentMode`, `enabled`, `createdAt`, `updatedAt`, `lastSeenAt`. The token hash is not exposed.

### 2.3 GET `/api/clients/{id}`

Returns one client by UUID.

- `200 OK` with the client.
- `500 Internal Server Error` if not found, because `ClientNotFoundException` is not mapped to 404 in the current code. Treat absence as an error, not as an empty result.

### 2.4 POST `/api/agent/heartbeat`

Updates `last_seen_at`. Requires bearer token.

Request: empty body.

Response `200 OK`:

```json
{
  "status": "ok",
  "clientId": "0f1c2d3e-4a5b-6c7d-8e9f-001122334455",
  "lastSeenAt": "2026-11-12T15:00:10+00:00"
}
```

Errors:

- `401 Unauthorized`: missing/malformed bearer token, unknown token, revoked/expired token, disabled client.

### 2.5 POST `/api/agent/telemetry`

Stores a CPU/memory resource sample for the authenticated client. Requires bearer token. This endpoint does **not** accept disk or network arrays; use the Express endpoint for those.

Request:

```json
{
  "experimentId": null,
  "agentId": "gateway-01",
  "observedAt": "2026-11-12T15:00:10+00:00",
  "cpuPercent": 23.5,
  "memoryTotalBytes": 8589934592,
  "memoryUsedBytes": 3221225472,
  "memoryAvailableBytes": 5368709120,
  "source": "measured_client",
  "collectionVersion": "1.0.0"
}
```

Validation:

- `observedAt` required.
- `cpuPercent` 0–100.
- Memory values required, non-negative, and each not greater than total.
- `source` required, one of `simulated`, `measured_client`, `estimated`, `unavailable`.

Response `201 Created`:

```json
{
  "sampleId": 101,
  "clientId": "0f1c2d3e-4a5b-6c7d-8e9f-001122334455",
  "experimentId": null,
  "observedAt": "2026-11-12T15:00:10+00:00",
  "cpuPercent": 23.5,
  "memoryTotalBytes": 8589934592,
  "memoryUsedBytes": 3221225472,
  "memoryAvailableBytes": 5368709120,
  "source": "measured_client"
}
```

Errors:

- `400 Bad Request`: missing fields, out-of-range CPU, invalid memory, unsupported source.
- `401 Unauthorized`: invalid or inactive credential.

Side effect: a successful telemetry post also updates `last_seen_at` and the credential's `last_used_at`.

### 2.6 GET `/api/dashboard/overview`

No authentication. Returns latest-per-client aggregates.

```json
{
  "totalClients": 3,
  "activeClients": 2,
  "runningExperiments": 0,
  "samplesToday": 42,
  "avgCpu": 31.2,
  "avgMemory": 54.7,
  "avgDisk": 61.0,
  "avgLatency": 18.4,
  "packetLoss": 0.3,
  "source": "measured_or_simulated_telemetry"
}
```

Definitions:

- `totalClients`: all rows in `clients`.
- `activeClients`: `last_seen_at` within the last five minutes.
- `runningExperiments`: `experiments.status = 'running'`.
- `samplesToday`: resource samples since local midnight.
- Averages use only the latest sample per client for each metric, so a chatty client does not dominate.
- Missing metrics contribute 0 through `COALESCE`; the dashboard should display them as unavailable where possible.

### 2.7 GET `/api/dashboard/clients`

No authentication. Returns one row per client with its latest resource, disk, and network values.

```json
[
  {
    "client_id": "0f1c2d3e-4a5b-6c7d-8e9f-001122334455",
    "display_name": "gateway-01",
    "agent_mode": "real_agent",
    "enabled": true,
    "last_seen_at": "2026-11-12T15:00:10+00:00",
    "cpu_percent": 23.5,
    "memory_percent": 37.5,
    "disk_percent": 61.0,
    "latency_ms": null,
    "packet_loss_percent": null,
    "source": "measured_client",
    "last_sample_at": "2026-11-12T15:00:10+00:00"
  }
]
```

Notes:

- `memory_percent` is computed as `memory_used_bytes * 100 / memory_total_bytes` and is `null` when total is zero.
- `source` falls back to `unavailable` when no resource sample exists.
- Disk and network values come from `disk_samples` and `network_samples`; they are null until the Express ingest writes them.
- Rows are ordered by `display_name`.

### 2.8 GET `/api/datasets/summary`

No authentication. Returns the packaged `dataset_report.json` verbatim: train/test row counts, column names, data types, missing-value counts, class counts, and class distributions. It does not read the CSV at request time.

## 3. Express endpoints

### 3.1 GET `/api/health`

```json
{ "success": true, "message": "GreenFed-IDS API is running", "status": "UP" }
```

### 3.2 GET `/api/db-health`

```json
{
  "success": true,
  "status": "CONNECTED",
  "database": "greenfed_monitor",
  "serverTime": "2026-11-12T15:00:00.000Z"
}
```

Returns `503` with `status: "DISCONNECTED"` if the database query fails.

### 3.3 POST `/api/clients`

Express registration. Requires `displayName` (at most 120 characters after trim) and `agentMode` (`real_agent` or `simulated_agent`). Returns `201` with `{ success, message, data: { client_id, display_name, agent_mode, enabled, created_at, clientToken } }`.

Errors: `400` for validation, `500` for persistence failure.

### 3.4 POST `/api/heartbeat`

Requires bearer token. Updates `last_seen_at` for an enabled client. Returns `200` with client identity and timestamp, `404` if the client is missing or disabled, `401` for invalid credentials.

### 3.5 POST `/api/telemetry`

Requires bearer token. Accepts the full agent payload:

```json
{
  "resource": {
    "cpuPercent": 23.5,
    "memoryTotalBytes": 8589934592,
    "memoryUsedBytes": 3221225472,
    "memoryAvailableBytes": 5368709120
  },
  "network": [
    {
      "interface": "eth0",
      "transferBytes": 123456,
      "durationMs": 10000,
      "bandwidthMbps": 12.3
    }
  ],
  "disk": [
    {
      "filesystem": "/dev/sda1",
      "mount": "/",
      "totalBytes": 500107862016,
      "usedBytes": 250053931008,
      "availableBytes": 250053931008,
      "usedPercent": 50.0
    }
  ]
}
```

Validation:

- `resource` required; CPU 0–100; memory non-negative and consistent (`used + available <= total + 1`).
- `network` and `disk` must be arrays (they may be empty), with the fields and ranges above. Invalid individual items are skipped by the service, but malformed array items are rejected by the controller.
- The sample source is derived from the authenticated client's `agent_mode`: `simulated_agent` writes `simulated`; `real_agent` writes `measured_client` / `measured_network`.

Response `201 Created`:

```json
{ "success": true, "message": "CPU, RAM, disk and network telemetry saved successfully" }
```

Errors: `400` for invalid measurements, `401` for invalid credentials, `500` for database failure.

### 3.6 Agent payload path

The Node agent posts to `${API_URL}/api/telemetry` with `Authorization: Bearer ${AGENT_TOKEN}`. Set `API_URL` to the Express service (port 5000) for the full payload, or adapt the agent to the Spring endpoint if disk/network ingest is moved. The agent's `.env` is not committed.

## 4. Versioning and compatibility

There is no version prefix. The Spring service and Express service are separate codebases with overlapping paths (`/api/clients`) but different response shapes:

- Spring returns bare client objects.
- Express returns `{ success, message, data }`.

The dashboard targets Spring (`/api/dashboard/*`, `/api/datasets/summary`). Do not point the dashboard at Express without adapting response parsing.

## 5. Error conventions

- Spring: standard HTTP status codes; `ResponseStatusException` produces a JSON error body with status, error, and message. Unmapped runtime exceptions (including `ClientNotFoundException`) become `500`.
- Express: `{ "success": false, "message": "..." }` with the appropriate status.
- Validation messages are human-readable and should not be treated as stable machine-readable codes.

## 6. Security notes

- Bearer tokens are stored as SHA-256 hashes, not plaintext.
- Registration returns the raw token once; there is no rotation or recovery endpoint.
- Dashboard endpoints are unauthenticated. Do not expose them on an untrusted network.
- CORS is open in the Express service; the Spring service relies on the development proxy. Production needs restrictive CORS.
- No rate limiting, request signing, TLS termination, or secure aggregation is implemented.

## 7. Examples

Register and post telemetry to Spring:

```powershell
$body = @{ displayName = "gateway-01"; agentMode = "real_agent" } | ConvertTo-Json
$response = Invoke-RestMethod -Method Post -Uri http://localhost:4000/api/clients `
  -ContentType "application/json" -Body $body
$token = $response.agentToken

$telemetry = @{
  observedAt = (Get-Date).ToUniversalTime().ToString("o")
  cpuPercent = 23.5
  memoryTotalBytes = 8589934592
  memoryUsedBytes = 3221225472
  memoryAvailableBytes = 5368709120
  source = "measured_client"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://localhost:4000/api/agent/telemetry `
  -Headers @{ Authorization = "Bearer $token" } `
  -ContentType "application/json" -Body $telemetry
```

Read dashboard aggregates:

```powershell
Invoke-RestMethod http://localhost:4000/api/dashboard/overview | ConvertTo-Json
Invoke-RestMethod http://localhost:4000/api/dashboard/clients | ConvertTo-Json -Depth 5
```
