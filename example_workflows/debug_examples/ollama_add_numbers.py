"""
Ollama Add Numbers Example

This example demonstrates using Ollama's OpenAI-compatible API.

Installation:
    # macOS
    brew install ollama

    # Linux
    curl -fsSL https://ollama.com/install.sh | sh

    # Windows: Download from https://ollama.com/download

Usage:
    # Start the Ollama server
    ollama serve

    # Pull a small model (in another terminal)
    ollama pull llama3.2:1b

    # Run this example
    ao-record ./example_workflows/debug_examples/ollama_add_numbers.py
"""

from openai import OpenAI


def main():
    model = "llama3.2:1b"
    # Connect to Ollama using OpenAI-compatible API
    client = OpenAI(
        base_url="http://localhost:11434/v1",
        api_key="ollama",  # Required by client but not used by Ollama
    )

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Output the number 42. ONLY output the number!"}],
        max_tokens=100,
        temperature=0.7,
    )

    number = response.choices[0].message.content

    prompt_add_1 = f"Add 1 to {number} and just output the result."
    prompt_add_2 = f"Add 2 to {number} and just output the result."

    response1 = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt_add_1}],
        max_tokens=100,
        temperature=0.7,
    )

    response2 = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt_add_2}],
        max_tokens=100,
        temperature=0.7,
    )

    result1 = response1.choices[0].message.content
    result2 = response2.choices[0].message.content

    sum_prompt = f"Add these two numbers together and just output the result: {result1} + {result2}"

    final_sum = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": sum_prompt}],
        max_tokens=100,
        temperature=0.7,
    )

    print(f"Final sum: {final_sum.choices[0].message.content}")


if __name__ == "__main__":
    main()
