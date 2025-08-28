from human_eval.data import write_jsonl, read_problems
import os
from anthropic import Anthropic
import random


# Generate one completion for a task using Claude Sonnet 3.5
def generate_one_completion(task_prompt):
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        messages=[{"role": "user", "content": task_prompt}],
        max_tokens=1000,
    )

    return response.content[0].text


# Read the problems and generate completions
problems = read_problems()

# Take a random subset of 5 problems
random.seed(42)
problems_subset = random.sample(list(problems.items()), 5)

num_samples_per_task = 1
samples = [
    dict(
        task_id=task_id,
        completion=generate_one_completion(problems[task_id]["prompt"]),
    )
    for task_id, _ in problems_subset
    for _ in range(num_samples_per_task)
]

write_jsonl("outputs/basic_samples.jsonl", samples)
