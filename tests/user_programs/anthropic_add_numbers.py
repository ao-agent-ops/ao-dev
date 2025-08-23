import os
import anthropic

# Ensure API key is set for testing
if not os.environ.get("ANTHROPIC_API_KEY"):
    print("[user_program] ANTHROPIC_API_KEY not set, setting dummy key")
    os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-dummy-key"

print(
    f"[user_program] Creating Anthropic client with API key: {os.environ.get('ANTHROPIC_API_KEY', 'NOT_SET')[:20]}..."
)
client = anthropic.Anthropic()
print(f"[user_program] Anthropic client created successfully")
model = "undefined_model"  # Make sure cache is used.


response = client.messages.create(
    model=model,
    max_tokens=10,
    messages=[{"role": "user", "content": "Output the number 42 and nothing else"}],
)

response_text = response.content[0].text

prompt_add_1 = f"Add 1 to {response_text} and just output the result."
prompt_add_2 = f"Add 2 to {response_text} and just output the result."

response1 = client.messages.create(
    model=model,
    max_tokens=10,
    messages=[{"role": "user", "content": prompt_add_1}],
)

response2 = client.messages.create(
    model=model,
    max_tokens=10,
    messages=[{"role": "user", "content": prompt_add_2}],
)

sum_prompt = f"Add these two numbers together and just output the result: {response1.content[0].text} + {response2.content[0].text}"

final_sum = client.messages.create(
    model=model,
    max_tokens=10,
    messages=[{"role": "user", "content": sum_prompt}],
)
