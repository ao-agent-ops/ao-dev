from human_eval.data import write_jsonl, read_problems
import os
from anthropic import Anthropic
import random


# Generate one completion for a task with 3 calls to Claude Sonnet 3.5
# The first call is to generate a plan,
# the second call is to generate the code,
# and the third call is to make sure the code is not buggy and return a finalized version of the code.
def generate_one_completion(task_prompt):
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Generate a plan
    plan_response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        messages=[
            {
                "role": "user",
                "content": f"You are an expert software engineer. Generate a step-by-step plan for the following task: {task_prompt}",
            }
        ],
        max_tokens=1000,
    )

    # Generate the code
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        messages=[
            {
                "role": "user",
                "content": f"You are an expert software engineer. Given the following task and plan, generate the code. IMPORTANT: Return only the code, no other text. The code should be valid Python code that can be executed. Task: {task_prompt}. Plan: {plan_response.content[0].text}",
            }
        ],
        max_tokens=1000,
    )

    # Make sure the code is not buggy and return a finalized version of the code.

    final_response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        messages=[
            {
                "role": "user",
                "content": f"You are an expert software engineer. Given the following task, plan, and code, make sure the code is not buggy and return a finalized version of the code. IMPORTANT: Return only the code, no other text. The code should be valid Python code that can be executed. Task: {task_prompt}. Plan: {plan_response.content[0].text}. Code: {response.content[0].text}.",
            }
        ],
        max_tokens=1000,
    )

    return final_response.content[0].text


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

write_jsonl("outputs/three_calls_samples.jsonl", samples)
