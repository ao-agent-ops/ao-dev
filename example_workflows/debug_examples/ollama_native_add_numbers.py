"""
Ollama Native Client Add Numbers Example

This example demonstrates using Ollama's native Python client with multiple features:
- Chat completions
- Tool/function calling

Installation:
    # Install Ollama
    # macOS: brew install ollama
    # Linux: curl -fsSL https://ollama.com/install.sh | sh
    # Windows: Download from https://ollama.com/download

    # Install the Python client
    pip install ollama

Usage:
    # Start the Ollama server
    ollama serve

    # Pull a model that supports tool calling (in another terminal)
    ollama pull llama3.2:1b

    # Run this example
    ao-record ./example_workflows/debug_examples/ollama_native_add_numbers.py
"""

import ollama


# Tool function - Ollama automatically extracts the schema from docstrings
def add_two_numbers(a: int, b: int) -> int:
    """
    Add two numbers together.

    Args:
        a: The first number
        b: The second number

    Returns:
        The sum of the two numbers
    """
    return a + b


def main():
    model = "llama3.2:1b"

    # Step 1: Ask the model to generate a number
    print("Step 1: Asking for a number...")
    response = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": "Output the number 42. ONLY output the number!"}],
    )
    number = response.message.content.strip()
    print(f"Got number: {number}")

    # Step 2: Use tool calling to add 1 and 2 to the number
    print("\nStep 2: Using tool calling to add numbers...")

    # Ask model to add 1
    response_add1 = ollama.chat(
        model=model,
        messages=[
            {
                "role": "user",
                "content": f"Use the add_two_numbers tool to add 1 to {number}. Call the tool now.",
            }
        ],
        tools=[add_two_numbers],
    )

    # Execute the tool call if the model made one
    result1 = None
    if response_add1.message.tool_calls:
        tool_call = response_add1.message.tool_calls[0]
        result1 = add_two_numbers(**tool_call.function.arguments)
        print(f"Tool call result (add 1): {result1}")
    else:
        # Fallback if model didn't use tool
        result1 = response_add1.message.content
        print(f"Model response (add 1): {result1}")

    # Ask model to add 2
    response_add2 = ollama.chat(
        model=model,
        messages=[
            {
                "role": "user",
                "content": f"Use the add_two_numbers tool to add 2 to {number}. Call the tool now.",
            }
        ],
        tools=[add_two_numbers],
    )

    result2 = None
    if response_add2.message.tool_calls:
        tool_call = response_add2.message.tool_calls[0]
        result2 = add_two_numbers(**tool_call.function.arguments)
        print(f"Tool call result (add 2): {result2}")
    else:
        result2 = response_add2.message.content
        print(f"Model response (add 2): {result2}")

    # Step 3: Get the final sum
    print("\nStep 3: Final calculation...")
    final_response = ollama.chat(
        model=model,
        messages=[
            {
                "role": "user",
                "content": f"Add these two numbers together: {result1} + {result2}. Just output the result.",
            }
        ],
    )

    print(f"Final sum: {final_response.message.content.strip()}")


if __name__ == "__main__":
    main()
