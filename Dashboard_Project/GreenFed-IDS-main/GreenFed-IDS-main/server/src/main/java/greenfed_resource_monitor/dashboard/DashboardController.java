package greenfed_resource_monitor.dashboard;

import java.util.List;
import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/dashboard")
public class DashboardController {

    private final DashboardService dashboardService;

    public DashboardController(DashboardService dashboardService) {
        this.dashboardService = dashboardService;
    }

    @GetMapping("/overview")
    public Map<String, Object> overview() {
        return dashboardService.overview();
    }

    @GetMapping("/clients")
    public List<Map<String, Object>> clients() {
        return dashboardService.clients();
    }

    @GetMapping("/timeseries")
    public Map<String, Object> timeseries() {
        return dashboardService.timeseries();
    }
}
