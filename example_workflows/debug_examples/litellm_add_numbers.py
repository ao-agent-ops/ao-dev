from litellm import completion

response = completion(
    model="openai/gpt-4o",
    max_tokens=10,
    messages=[{"role": "user", "content": "Output the number 42 and nothing else"}],
)

# Fix: Use the correct response structure
response_text = response.choices[0].message.content

prompt_add_1 = f"Add 1 to {response_text} and just output the result."
prompt_add_2 = f"Add 2 to {response_text} and just output the result."

response1 = completion(
    model="openrouter/openai/gpt-3.5-turbo",
    max_tokens=10,
    messages=[{"role": "user", "content": prompt_add_1}],
)

# Fix: Use the correct response structure
response1_text = response1.choices[0].message.content

response2 = completion(
    model="anthropic/claude-sonnet-4-20250514",
    max_tokens=10,
    messages=[{"role": "user", "content": prompt_add_2}],
)

# Fix: Use the correct response structure
response2_text = response2.choices[0].message.content

sum_prompt = f"Add these two numbers together and just output the result: {response1_text} + {response2_text}"

final_sum = completion(
    model="anthropic/claude-3-7-sonnet-20250219",
    max_tokens=10,
    messages=[{"role": "user", "content": sum_prompt}],
)

# Fix: Use the correct response structure
final_sum_text = final_sum.choices[0].message.content

print(f"Original number: {response_text}")
print(f"Number + 1: {response1_text}")
print(f"Number + 2: {response2_text}")
print(f"Final sum: {final_sum_text}")
