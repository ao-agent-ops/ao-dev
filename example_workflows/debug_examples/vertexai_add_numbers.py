from google import genai
from google.genai.types import HttpOptions

model = "gemini-2.5-flash"

# Create a Vertex AI client using default credentials
client = genai.Client(http_options=HttpOptions(api_version="v1"))

response = client.models.generate_content(
    model=model,
    contents="Output the number 42 and nothing else",
)

response = response.text

print("RESPONSE", response)

prompt_add_1 = f"Add 1 to {response} and just output the result."
prompt_add_2 = f"Add 2 to {response} and just output the result."

print("PROMPT ADD 1", prompt_add_1)
print("PROMPT ADD 2", prompt_add_2)

response1 = client.models.generate_content(
    model=model,
    contents=prompt_add_1,
)

response2 = client.models.generate_content(
    model=model,
    contents=prompt_add_2,
)

sum_prompt = f"Add these two numbers together and just output the result: {response1.text} + {response2.text}"

final_sum = response = client.models.generate_content(
    model=model,
    contents=sum_prompt,
)