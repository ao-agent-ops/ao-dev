#!/usr/bin/env python3
"""
Writer script that generates random content and writes it to a file.
"""

import os
from openai import OpenAI

client = OpenAI()

print("=== Writer Session ===")
print(f"Session ID: {os.environ.get('AGENT_COPILOT_SESSION_ID', 'unknown')}")

# Generate random content
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "user", "content": "Write a short creative story about robots and humans working together. Make it 2-3 paragraphs."}
    ]
)

content = response.choices[0].message.content

# Write to file
current_dir = os.path.dirname(os.path.abspath(__file__))
output_file = os.path.join(current_dir, "content.txt")

print(f"Writing content to {output_file}")

with open(output_file, "w") as f:
    f.write(content)

print(f"Content written to {output_file}")
print("Run openai_document_reader.py next to see cross-session taint tracking!")