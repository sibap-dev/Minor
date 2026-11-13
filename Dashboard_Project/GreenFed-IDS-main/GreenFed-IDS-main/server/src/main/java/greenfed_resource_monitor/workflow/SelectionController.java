package greenfed_resource_monitor.workflow;

import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/selection")
public class SelectionController {

    private final SelectionService selectionService;

    public SelectionController(SelectionService selectionService) {
        this.selectionService = selectionService;
    }

    @PostMapping
    public Map<String, Object> execute(@RequestBody SelectionRequest request) {
        return selectionService.execute(request);
    }

    @GetMapping("/latest")
    public Map<String, Object> latest() {
        return selectionService.latest();
    }

    @GetMapping("/{selectionId}")
    public Map<String, Object> get(@PathVariable String selectionId) {
        return selectionService.get(selectionId);
    }
}
