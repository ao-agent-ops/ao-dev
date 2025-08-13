import anthropic


client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=10,
    messages=[{"role": "user", "content": "Output the number 42 and nothing else"}],
)

response_text = response.content[0].text

prompt_add_1 = f"Add 1 to {response_text} and just output the result."
prompt_add_2 = f"Add 2 to {response_text} and just output the result."

response1 = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=10,
    messages=[{"role": "user", "content": prompt_add_1}],
)

response2 = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=10,
    messages=[{"role": "user", "content": prompt_add_2}],
)

sum_prompt = f"Add these two numbers together and just output the result: {response1.content[0].text} + {response2.content[0].text}"

final_sum = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=10,
    messages=[{"role": "user", "content": sum_prompt}],
)
