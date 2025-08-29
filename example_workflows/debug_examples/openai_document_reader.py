#!/usr/bin/env python3
"""
Script that reads the output from openai_document_writer.py.
This demonstrates cross-session taint tracking - the node created here
will be added to the same graph as the writer session.
File operations are automatically wrapped with TaintFile through monkey patching.
"""

import os
import sys
from openai import OpenAI

client = OpenAI()
model = "gpt-3.5-turbo"

current_dir = os.path.dirname(os.path.abspath(__file__))
input_file = os.path.join(current_dir, "document_summary.txt")

print("=== Document Reader Session ===")
print(f"Session ID: {os.environ.get('AGENT_COPILOT_SESSION_ID', 'unknown')}")

if not os.path.exists(input_file):
    print(f"Error: {input_file} not found.")
    print("Please run openai_document_writer.py first.")
    sys.exit(1)

print(f"\nReading summary from {input_file}")

# Read the summary (automatically wrapped with TaintFile through monkey patching)
with open(input_file, "r") as f:
    content = f.read()

print(f"Read {len(content)} characters from file")

# The content should automatically have taint from the previous session
# due to the monkey-patched open() function

# Extract just the summary part
summary_start = content.find("--- Summary ---")
summary_end = content.find("=== End of Results ===")
if summary_start != -1 and summary_end != -1:
    summary_text = content[summary_start:summary_end].strip()
else:
    summary_text = content

print("\n--- Processing tainted summary ---")

# Use the tainted summary in a new LLM call
# This creates a new node that depends on the nodes from the writer session
response = client.chat.completions.create(
    model=model,
    messages=[
        {"role": "system", "content": "You are an expert at creating bullet points."},
        {"role": "user", "content": f"Convert this summary into 3 bullet points:\n\n{summary_text[:1000]}"}
    ]
)

bullet_points = response.choices[0].message.content
print("\nGenerated bullet points:")
print(bullet_points)

# Write the bullet points to a new file (continuing the chain)
output_file = os.path.join(current_dir, "document_bullets.txt")
with open(output_file, "w") as f:
    f.write("=== Bullet Point Summary ===\n")
    f.write(f"Source: {input_file}\n")
    f.write("\n")
    f.write(bullet_points)
    f.write("\n\n=== End ===\n")

print(f"\nBullet points written to {output_file}")

print("\n=== CROSS-SESSION TAINT TRACKING ===")
print("Expected behavior in Agent Copilot UI:")
print("1. The writer session created nodes for generating the summary")
print("2. This reader session created a node for bullet points")
print("3. There should be edges connecting the reader node to writer nodes")
print("4. This demonstrates data flow across different program executions!")