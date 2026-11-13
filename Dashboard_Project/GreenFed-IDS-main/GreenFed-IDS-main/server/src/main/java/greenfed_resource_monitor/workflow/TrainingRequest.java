package greenfed_resource_monitor.workflow;

public record TrainingRequest(
        String name,
        String selectionId,
        String scenario,
        Integer seed,
        Integer rounds,
        Integer localEpochs,
        Integer batchSize,
        Double learningRate,
        Double validationFraction,
        Integer maxSamplesPerClient,
        String classWeightMode,
        Integer numThreads) {
}
