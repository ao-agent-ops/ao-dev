import time
from openai import OpenAI
client = OpenAI()


response = client.responses.create(
    model="gpt-3.5-turbo",
    input="Output the number 42 and nothing else"
)

response = response.output_text

prompt_add_1 = f"Add 1 to {response} and just output the result."
prompt_add_2 = f"Add 2 to {response} and just output the result."

response1 = client.responses.create(
    model="gpt-3.5-turbo",
    input=prompt_add_1
)

response2 = client.responses.create(
    model="gpt-3.5-turbo",
    input=prompt_add_2
)

sum_prompt = f"Add these two numbers together and just output the result: {response1.output_text} + {response2.output_text}"

final_sum = client.responses.create(
    model="gpt-3.5-turbo",
    input=sum_prompt
)
