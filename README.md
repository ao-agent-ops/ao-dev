# AO Agent Dev: What-if Questions over Agent Trajectories  

AO Agent Dev is a developer tool for agent builders. It supports arbitrary Python progams (like your existing agents!) and will visualize your agent's LLM and MCP calls into a dataflow graph. You can then inspect, edit and rerun this graph and understand how to fix your agent.

[![Quickstart video](docs/media/quickstart_screenshot.png)](https://youtu.be/woVctiSRJU0)


## Quickstart

`AO Agent Dev` integrates into VS Code or IDEs based on it, like Cursor. 

Simply download (1) our [VS Code Extension](https://marketplace.visualstudio.com/items?itemName=agentops.ao-agent-dev) (type ao dev into the marketplace search and install the one with the blue icon by "Agent Ops"), (2) install our pip package:

```bash
pip install ao-dev
```

Or if you use [uv](https://docs.astral.sh/uv/):

```bash
uv add ao-dev
```

**Then, give it a spin:**

1. Create some little agent program that you want to run (or use your existing agent!). For example, you can try this little OpenAI example below (or find many further example scripts in our [examples folder](/example_workflows/debug_examples/)):

```python
from openai import OpenAI


def main():
    client = OpenAI()

    # First LLM: Generate a yes/no question
    question_response = client.responses.create(
        model="gpt-4o-mini",
        input="Come up with a simple question where there is a pro and contra opinion. Only output the question and nothing else.",
        temperature=0,
    )
    question = question_response.output_text

    # Second LLM: Argue "yes"
    yes_prompt = f"Consider this question: {question}\nWrite a short paragraph on why to answer this question with 'yes'"
    yes_response = client.responses.create(
        model="gpt-4o-mini", input=yes_prompt, temperature=0
    )

    # Third LLM: Argue "no"
    no_prompt = f"Consider this question: {question}\nWrite a short paragraph on why to answer this question with 'no'"
    no_response = client.responses.create(
        model="gpt-4o-mini", input=no_prompt, temperature=0
    )

    # Fourth LLM: Judge who won
    judge_prompt = f"Consider the following two paragraphs:\n1. {yes_response.output_text}\n2. {no_response.output_text}\nWho won the argument?"
    judge_response = client.responses.create(
        model="gpt-4o-mini", input=judge_prompt, temperature=0
    )

    print(f"Question: {question}")
    print(f"\nJudge's verdict: {judge_response.output_text}")

if __name__ == "__main__":
    main()
```

2. Run the script with python to verify it works (keys are set correctly, etc.):

```bash
python openai_example.py
```

3. Run the script using `ao-record`.

```bash
ao-record openai_example.py
```

This should show you the agent's trajectory graph like in the video above. You can edit inputs and outputs in the graph and rerun.

## Documentation

For complete documentation, installation guides, and tutorials, visit our **[Documentation Site](https://ao-agent-ops.github.io/ao-dev/)**.

## Building from source and developing

See the [Installation Guide](https://ao-agent-ops.github.io/ao-dev/getting-started/installation/) for development setup and the [Developer Guide](https://ao-agent-ops.github.io/ao-dev/developer-guide/architecture/) for architecture details. More details can also be found in the READMEs of the corresponding dirs in `src/`.

## Community

- [Join our Discord](https://discord.gg/fjsNSa6TAh)
- [GitHub Issues](https://github.com/agent-ops-project/ao-dev/issues)
- We're just getting started on this tool and are eager to hear your feedback and resolve issues you ran into! We hope you enjoy it as much as we do.
