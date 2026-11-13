package greenfed_resource_monitor.workflow;

import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/simulation")
public class SimulationController {

    private final SimulationService simulationService;

    public SimulationController(SimulationService simulationService) {
        this.simulationService = simulationService;
    }

    @GetMapping("/status")
    public Map<String, Object> status() {
        return simulationService.status();
    }

    @PostMapping("/start")
    public Map<String, Object> start() {
        return simulationService.start();
    }

    @PostMapping("/stop")
    public Map<String, Object> stop() {
        return simulationService.stop();
    }
}
