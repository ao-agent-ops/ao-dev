"""
vLLM Add Numbers Example

This example demonstrates using vLLM's OpenAI-compatible API server.

To run this example:

1. Install vLLM

    conda create -n vllm python=3.13 -y
    conda activate vllm
    git clone https://github.com/vllm-project/vllm.git
    pip install torch torchvision
    cd vllm && VLLM_TARGET_DEVICE=cpu VLLM_BUILD_WITH_CUDA=0 pip install -e .

1. Start a vLLM server:

   VLLM_USE_CUDA=0 python -m vllm.entrypoints.openai.api_server \
        --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
        --tensor-parallel-size 1 \
        --host 0.0.0.0 \
        --port 8000 \
        --dtype float16

2. Run this script:

   ao-record ./example_workflows/debug_examples/vllm_add_numbers.py

Note: vLLM provides an OpenAI-compatible API, so we use the OpenAI client
with a custom base_url pointing to the vLLM server.
"""

from openai import OpenAI


def main():
    model = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    # Connect to vLLM server using OpenAI-compatible API
    # The api_key is not used by vLLM but required by the OpenAI client
    client = OpenAI(
        base_url="http://localhost:8000/v1",
        api_key="not-needed",
    )

    # Use chat completions API (vLLM's primary supported endpoint)
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