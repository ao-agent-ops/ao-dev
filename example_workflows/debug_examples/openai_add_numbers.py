import time
start = time.time()

from openai import OpenAI

import_time = time.time()
print("UNTIL IMPORT", import_time - start)

client = OpenAI()

response = client.responses.create(
    model="gpt-3.5-turbo", input=f"Output the number 42 and nothing else", temperature=0
)

response = response.output_text

prompt_add_1 = f"Add 1 to {response} and just output the result."
prompt_add_2 = f"Add 2 to {response} and just output the result."

response1 = client.responses.create(model="gpt-3.5-turbo", input=prompt_add_1, temperature=0)

response2 = client.responses.create(model="gpt-3.5-turbo", input=prompt_add_2, temperature=0)

sum_prompt = f"Add these two numbers together and just output the result: {response1.output_text} + {response2.output_text}"

final_sum = client.responses.create(model="gpt-3.5-turbo", input=sum_prompt, temperature=0)

print("Total:", time.time() - start)
print("no import:", time.time() - import_time)

# UNTIL IMPORT 1.0484449863433838
# Total: 11.300607919692993
# no import: 10.252225875854492

# UNTIL IMPORT 0.05247020721435547
# Total: 11.551378965377808
# no import: 11.66481876373291