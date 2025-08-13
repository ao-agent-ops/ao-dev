#!/usr/bin/env python3
"""
Simple test file to verify CodeQL LLM taint analysis works
This file contains patterns that should be detected by the analysis
"""

import openai
from language_model import LANGUAGE_MODEL


client = openai.OpenAI(api_key="test-key")

# class Agent:
#     def __init__(self):
#         self.client = openai.OpenAI(api_key="test-key")

#     def run(self, x):
#         return self.client.chat.completions.create(
#             model="gpt-4",
#             messages=[{"role": "user", "content": x}]
#             )


# def test_llm_taint_flow():
#     """Test function with LLM taint flow"""

#     a = Agent()
#     x = a.run("hello")

#     # y = LANGUAGE_MODEL.parse_standard_response(x)

#     y = {"key": x}
#     # y["key"] = x
#     y = a.run(y)

# if __name__ == "__main__":
#     test_llm_taint_flow()


# ########################## WORKS: #########################
# x = client.chat.completions.create(model="gpt-4", messages=[{"role": "user", "content": "hello"}])
# y = {"key": x}
# client.chat.completions.create(model="gpt-4", messages=[{"role": "user", "content": y}])


# ###################### DOESN'T WORK: ######################
# x = client.chat.completions.create(model="gpt-4", messages=[{"role": "user", "content": "hello"}])
# y = {}
# y["key"] = x
# client.chat.completions.create(model="gpt-4", messages=[{"role": "user", "content": y}])


####################### DOESN'T WORK ######################
x = client.chat.completions.create(model="gpt-4", messages=[{"role": "user", "content": "hello"}])
y = obfuscated_fn(x)  # e.g., cursor.execute(x) to run DB query
client.chat.completions.create(model="gpt-4", messages=[{"role": "user", "content": y}])
