# Subruns

Subruns allow you to create separate tracked sessions within a single `aco-launch` execution. This is particularly useful for evaluation scripts where you want each sample to be tracked independently.

## Basic Usage

Use the `aco_launch` context manager to create subruns:

```python
from aco.runner.context_manager import aco_launch

for sample in samples:
    with aco_launch("sample-name"):
        eval_sample(sample)
```

Each iteration creates a separate run in the Agent Copilot UI, allowing you to:

- View each sample's dataflow graph independently
- Compare results across samples
- Debug specific failed samples

## Naming Subruns

Give descriptive names to your subruns for easy identification:

```python
for i, sample in enumerate(samples):
    with aco_launch(f"sample-{i}-{sample.id}"):
        result = process_sample(sample)
```

## Concurrent Subruns

Subruns can run concurrently using Python's threading or multiprocessing:

```python
from concurrent.futures import ThreadPoolExecutor
from aco.runner.context_manager import aco_launch

def process_sample(sample):
    with aco_launch(f"sample-{sample.id}"):
        return run_evaluation(sample)

with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(process_sample, samples))
```

Each concurrent subrun maintains its own context and appears as a separate run in the UI.

## How It Works

When you enter a subrun context:

1. A new session ID is generated
2. The server is notified of the new session
3. All LLM calls within the context are associated with that session
4. The dataflow graph is built for that specific session

When the context exits, the session is closed and the graph is finalized.

![Subruns Architecture](../assets/images/subrun.png)

## Use Cases

### Evaluation Pipelines

```python
results = []
for sample in test_dataset:
    with aco_launch(f"eval-{sample.id}"):
        prediction = agent.run(sample.input)
        score = evaluate(prediction, sample.expected)
        results.append(score)

print(f"Average score: {sum(results) / len(results)}")
```

### A/B Testing

```python
configs = [
    {"model": "gpt-4", "temperature": 0.7},
    {"model": "gpt-4", "temperature": 0.2},
]

for config in configs:
    with aco_launch(f"config-{config['model']}-t{config['temperature']}"):
        run_benchmark(config)
```

### Debugging Specific Cases

```python
failed_samples = [s for s in samples if s.status == "failed"]

for sample in failed_samples:
    with aco_launch(f"debug-{sample.id}"):
        # Run with verbose logging
        result = agent.run(sample.input, verbose=True)
```

## Examples

See the `example_workflows/debug_examples/` directory for working examples of subruns in action.

## Next Steps

- [Explore example workflows](../examples/index.md)
- [Learn about the architecture](../developer-guide/architecture.md)
