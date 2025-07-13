#!/usr/bin/env python3

from openai import OpenAI

# Test script to verify graph display is working
print("Testing graph display with OpenAI call...")

client = OpenAI()

# This should create a node in the graph
response = client.responses.create(
    model="gpt-4o-mini",
    input="Write a short poem about debugging."
)

print("Response received:")
print(response.output_text)
print("Test completed!") 