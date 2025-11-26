from together import Together


def main():

    client = Together()

    model = "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8"

    # First LLM call: Get the number 42
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Output the number 42 and nothing else"}],
        temperature=0,
    )

    response_text = response.choices[0].message.content

    # Two parallel LLM calls: Add 1 and Add 2
    prompt_add_1 = f"Add 1 to {response_text} and just output the result."
    prompt_add_2 = f"Add 2 to {response_text} and just output the result."

    response1 = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt_add_1}],
        temperature=0,
    )

    response2 = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt_add_2}],
        temperature=0,
    )

    # Final LLM call: Sum the two results
    sum_prompt = f"Add these two numbers together and just output the result: {response1.choices[0].message.content} + {response2.choices[0].message.content}"

    final_sum = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": sum_prompt}],
        temperature=0,
    )

    print(f"Final result: {final_sum.choices[0].message.content}")


if __name__ == "__main__":
    main()