package greenfed_resource_monitor.workflow;

import java.util.List;
import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/experiments")
public class ExperimentController {

    private final ExperimentHistoryService historyService;

    public ExperimentController(ExperimentHistoryService historyService) {
        this.historyService = historyService;
    }

    @GetMapping
    public List<Map<String, Object>> list() {
        return historyService.list();
    }

    @GetMapping("/{runId}")
    public Map<String, Object> get(@PathVariable String runId) {
        return historyService.get(runId);
    }

    @GetMapping("/{runId}/strategy/{strategy}")
    public Map<String, Object> strategy(
            @PathVariable String runId,
            @PathVariable String strategy) {
        return historyService.strategyResults(runId, strategy);
    }
}
