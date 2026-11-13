
package greenfed_resource_monitor.dataset;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.util.Map;

@Service
public class DatasetService {

    private final ObjectMapper objectMapper = new ObjectMapper();

    public Map<String, Object> getDatasetSummary() {
        try {
            ClassPathResource resource =
                    new ClassPathResource("dataset/dataset_report.json");

            return objectMapper.readValue(
                    resource.getInputStream(),
                    new TypeReference<Map<String, Object>>() {}
            );

        } catch (IOException e) {
            throw new RuntimeException(
                    "Unable to load dataset report", e
            );
        }
    }
}
