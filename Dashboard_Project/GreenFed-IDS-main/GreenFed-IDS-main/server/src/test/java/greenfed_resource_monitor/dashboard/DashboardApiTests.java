package greenfed_resource_monitor.dashboard;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class DashboardApiTests {

    @LocalServerPort
    private int port;

    private final ObjectMapper objectMapper = new ObjectMapper();

    private final HttpClient httpClient = HttpClient.newHttpClient();

    private String get(String path) throws Exception {
        HttpRequest request = HttpRequest.newBuilder(
                URI.create("http://localhost:" + port + path)
        ).GET().build();
        HttpResponse<String> response = httpClient.send(
                request, HttpResponse.BodyHandlers.ofString()
        );
        assertEquals(200, response.statusCode(), response.body());
        return response.body();
    }

    @Test
    void overviewReturnsAggregates() throws Exception {
        JsonNode body = objectMapper.readTree(get("/api/dashboard/overview"));
        for (String key : new String[] {
                "totalClients", "activeClients", "runningExperiments",
                "samplesToday", "avgCpu", "avgMemory", "avgDisk",
                "avgLatency", "packetLoss" }) {
            assertTrue(body.has(key), "missing key: " + key);
        }
    }

    @Test
    void clientsReturnsAnArray() throws Exception {
        JsonNode body = objectMapper.readTree(get("/api/dashboard/clients"));
        assertTrue(body.isArray());
    }
}
