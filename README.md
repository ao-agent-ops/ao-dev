# AO: Automatic Agent Tracing and Optimization

[![Discord](https://img.shields.io/badge/Discord-Join%20us-7289da?logo=discord&logoColor=white)](https://discord.gg/fjsNSa6TAh)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](https://github.com/agent-ops-project/agops-platform)

A development tool that creates interactive dataflow graphs of agent traces, enabling visualization, editing, and debugging of data flow in agentic systems – **with zero code changes**.

## Overview

AO goes beyond being a simple observability tool:

- **Visualize agent traces as a DAG** - See how data flows between LLM and tool calls in your application
- **Edit inputs and outputs** - Modify LLM and tool call inputs/outputs and **re-run** with changes, where previous nodes in the DAG are cached
- **Debug dataflow** - Track how LLM outputs propagate through your code

![AO VS Code Extension](docs/assets/images/demo-extension.png)

## Quickstart

```bash
pip install ao-agent-dev
```

Install the [AO VS Code Extension](https://marketplace.visualstudio.com/items?itemName=agentops.ao-agent-dev) from the VS Code marketplace.

### Step 1: Create an Example Project

Create a folder called `my-agent` and add a file called `openai_example.py` with the following content:

```python
from openai import OpenAI

def main():
    client = OpenAI()

    response = client.responses.create(
        model="gpt-4o-mini",
        input="Output the number 42 and nothing else",
        temperature=0
    )
    number = response.output_text

    prompt_add_1 = f"Add 1 to {number} and just output the result."
    prompt_add_2 = f"Add 2 to {number} and just output the result."

    response1 = client.responses.create(model="gpt-4o-mini", input=prompt_add_1, temperature=0)
    response2 = client.responses.create(model="gpt-4o-mini", input=prompt_add_2, temperature=0)

    sum_prompt = f"Add these two numbers together and just output the result: {response1.output_text} + {response2.output_text}"
    final_sum = client.responses.create(model="gpt-4o-mini", input=sum_prompt, temperature=0)

    print(f"Final sum: {final_sum.output_text}")

if __name__ == "__main__":
    main()
```

Run the script to verify it works:

```bash
cd my-agent
python openai_example.py
```

The output should be `88` (42 + 1 = 43, 42 + 2 = 44, 43 + 44 = 87... well, roughly 88 depending on the model).

### Step 2: Configure AO

Run `ao-config` and set the project root to your `my-agent` folder:

```bash
ao-config
```

### Step 3: Start the Server

Start the AO server:

```bash
ao-server start
```

### Step 4: Run with AO

Open your `my-agent` folder in VS Code, then run the example with AO in the terminal:

```bash
ao-record openai_example.py
```

The VS Code extension will display the dataflow graph showing how data flows between the LLM calls.

## Documentation

For complete documentation, installation guides, and tutorials, visit our **[Documentation Site](https://agent-ops-project.github.io/agops-platform/)**.

## For Developers

See the [Installation Guide](https://agent-ops-project.github.io/agops-platform/getting-started/installation/#developer-installation) for development setup and the [Developer Guide](https://agent-ops-project.github.io/agops-platform/developer-guide/architecture/) for architecture details.

## Community

- [Join our Discord](https://discord.gg/fjsNSa6TAh)
- [GitHub Issues](https://github.com/agent-ops-project/agops-platform/issues)
