import anthropic


client = anthropic.Anthropic()

print("=== First API Call ===")
print("Input: Output the number 42 and nothing else")

response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=10,
    messages=[
        {
            "role": "user",
            "content": "Output the number 42 and nothing else"
        }
    ]
)

response_text = response.content[0].text
print(f"Output: {response_text}")
print()

prompt_add_1 = f"Add 1 to {response_text} and just output the result."
prompt_add_2 = f"Add 2 to {response_text} and just output the result."

print("=== Second API Call ===")
print(f"Input: {prompt_add_1}")

response1 = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=10,
    messages=[
        {
            "role": "user",
            "content": prompt_add_1
        }
    ]
)

print(f"Output: {response1.content[0].text}")
print()

print("=== Third API Call ===")
print(f"Input: {prompt_add_2}")

response2 = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=10,
    messages=[
        {
            "role": "user",
            "content": prompt_add_2
        }
    ]
)

print(f"Output: {response2.content[0].text}")
print()

sum_prompt = f"Add these two numbers together and just output the result: {response1.content[0].text} + {response2.content[0].text}"

print("=== Fourth API Call ===")
print(f"Input: {sum_prompt}")

final_sum = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=10,
    messages=[
        {
            "role": "user",
            "content": sum_prompt
        }
    ]
)

print(f"Output: {final_sum.content[0].text}")
print()
print("=== Final Result ===")
print(f"Final sum: {final_sum.content[0].text}")
