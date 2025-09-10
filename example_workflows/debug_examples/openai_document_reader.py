#!/usr/bin/env python3
"""
Reader script that reads content from writer and generates more content.
"""

import os
import sys
from openai import OpenAI

client = OpenAI()

current_dir = os.path.dirname(os.path.abspath(__file__))
input_file = os.path.join(current_dir, "content.txt")

print("=== Reader Session ===")
print(f"Session ID: {os.environ.get('AGENT_COPILOT_SESSION_ID', 'unknown')}")

if not os.path.exists(input_file):
    print(f"Error: {input_file} not found.")
    print("Please run openai_document_writer.py first.")
    sys.exit(1)

print(f"Reading content from {input_file}")

# Read the content
with open(input_file, "r") as f:
    content = f.read()

print(f"Read {len(content)} characters from file")

# Generate additional content based on the input
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "user", "content": f"Continue this story with another paragraph:\n\n{content}"}
    ]
)

additional_content = response.choices[0].message.content

# Write combined content to new file
output_file = os.path.join(current_dir, "extended_content.txt")

print(f"Writing extended content to {output_file}")

with open(output_file, "w") as f:
    f.write(content)
    f.write("\n\n--- CONTINUATION ---\n\n")
    f.write(additional_content)

print(f"Extended content written to {output_file}")
print("Cross-session taint tracking should connect the reader node to writer nodes!")