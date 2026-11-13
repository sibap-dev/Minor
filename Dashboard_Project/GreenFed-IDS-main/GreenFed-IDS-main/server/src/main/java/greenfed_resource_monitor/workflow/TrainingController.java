package greenfed_resource_monitor.workflow;

import java.util.List;
import java.util.Map;
import java.util.UUID;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/training")
public class TrainingController {

    private final TrainingService trainingService;

    public TrainingController(TrainingService trainingService) {
        this.trainingService = trainingService;
    }

    @PostMapping("/jobs")
    public Map<String, Object> start(@RequestBody TrainingRequest request) {
        return trainingService.start(request);
    }

    @GetMapping("/jobs")
    public List<Map<String, Object>> list() {
        return trainingService.list();
    }

    @GetMapping("/jobs/{jobId}")
    public Map<String, Object> get(@PathVariable UUID jobId) {
        return trainingService.get(jobId);
    }

    @PostMapping("/jobs/{jobId}/cancel")
    public Map<String, Object> cancel(@PathVariable UUID jobId) {
        return trainingService.cancel(jobId);
    }
}
